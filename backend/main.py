"""Campus Customs API: the file Uvicorn runs.

  cd backend
  uvicorn main:app --reload --port 8000

Sections:
- Accounts (Problem 4): sign-up, log-in, log-out, password hashing and signed session cookies.
- Product photos (Problems 9-10): white-backed display copies and print artwork, built in parallel.
- API (Problems 3, 5, 7, 8, 9): products, images, chat (plain + streaming) and chat history.

The agent itself is four files next to this one: prompts/prompt.md, agent.py, tools.py and models.py.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel, Field

from agent import run_chat, stream_chat
from models import ChatRequest, ChatResponse, ChatTurn, CustomerProfile, ProductDetail, SearchFilters
from tools import load_all_products, load_product, matches_for, redact_sensitive, search_with


# ========================================================================================
# Accounts (Problem 4)
# ========================================================================================
# Accounts: password hashing, sign-up, log-in, and signed session cookies (Problem 4).
#
# Passwords are never stored. Each user row keeps only a salted PBKDF2-SHA256 hash:
#
#     seed accounts: pbkdf2_sha256$<salt>$<hex digest>                 (120,000 iterations)
#     new accounts:  pbkdf2_sha256$<iterations>$<salt>$<hex digest>    (600,000 iterations)
#
# Both formats are accepted at log-in, so the provided accounts keep working.

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"

ALGORITHM = "pbkdf2_sha256"
LEGACY_ITERATIONS = 120_000  # what the seed database's 3-part hashes use
ITERATIONS = 600_000  # OWASP's current recommendation for PBKDF2-SHA256

SESSION_COOKIE = "cc_session"
SESSION_TTL = 7 * 24 * 3600  # one week

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 15 * 60

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- Password hashing ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"{ALGORITHM}${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 3:
        algo, salt, digest = parts
        iterations = LEGACY_ITERATIONS
    elif len(parts) == 4:
        algo, iter_text, salt, digest = parts
        iterations = int(iter_text)
    else:
        return False
    if algo != ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return hmac.compare_digest(candidate, digest)  # constant time, so timing leaks nothing


# A real hash to check against when the email doesn't exist, so a wrong email takes as
# long as a wrong password and response times don't reveal which emails have accounts.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- Signed session cookies ----------

def _load_secret() -> bytes:
    """Signing key from SESSION_SECRET, else a random key kept in data/ (git-ignored)."""
    if os.environ.get("SESSION_SECRET"):
        return os.environ["SESSION_SECRET"].encode()
    path = DATA_DIR / ".session_secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip().encode()


SECRET = _load_secret()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_session_token(user_id: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL}).encode())
    sig = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session_token(token: str) -> int | None:
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        return int(data["uid"]) if data["exp"] > time.time() else None
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        max_age=SESSION_TTL,
        httponly=True,  # page scripts can't read it, so injected JavaScript can't steal it
        samesite="lax",  # not sent on cross-site form posts
        secure=os.environ.get("COOKIE_SECURE") == "1",  # turn on when served over HTTPS
    )


# ---------- Database helpers ----------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def public_user(row: sqlite3.Row) -> dict:
    """The only user fields ever sent to the browser. The hash never leaves the server."""
    return {
        "id": row["id"],
        "first_name": row["first_name"] or row["name"].split(" ")[0],
        "last_name": row["last_name"] or "",
        "email": row["email"],
    }


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(token) if token else None
    if user_id is None:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


# ---------- Brute-force protection ----------

_failed: dict[str, list[float]] = {}


def _recent_failures(email: str) -> list[float]:
    cutoff = time.time() - LOCKOUT_SECONDS
    _failed[email] = [t for t in _failed.get(email, []) if t > cutoff]
    return _failed[email]


# ---------- Routes ----------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, response: Response) -> dict:
    email = body.email.strip().lower()
    first, last = body.first_name.strip(), body.last_name.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if not first or not last:
        raise HTTPException(400, "Please enter your first and last name.")
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists. Try logging in.")
        cur = conn.execute(
            "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
            (f"{first} {last}", first, last, email, hash_password(body.password)),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    set_session_cookie(response, row["id"])
    return public_user(row)


@router.post("/login")
def login(body: LoginRequest, response: Response) -> dict:
    email = body.email.strip().lower()
    if len(_recent_failures(email)) >= MAX_FAILED_LOGINS:
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    ok = verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH)
    if not (row and ok):
        _failed[email].append(time.time())
        # Same message either way, so attackers can't learn which emails are registered.
        raise HTTPException(401, "Incorrect email or password.")
    _failed.pop(email, None)
    set_session_cookie(response, row["id"])
    return public_user(row)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return user


# ========================================================================================
# Product photos (Problems 9-10)
# ========================================================================================
# Give every product photo a white background (front-end improvement 2).
#
# 73 of the 102 provided photos have a pure-black backdrop, which hides navy and dark
# garments, and some light photos have black bars down the sides. This flood-fills every
# black area touching the image border (only near-black pixels
# connected to the edge, so the garment and any black print inside it are untouched) and
# writes white-backed copies to data/products_display/. The originals are never changed.
#
# The photos are processed in parallel, one worker process per CPU core (Problem 9, backend
# improvement 3): each photo is independent CPU work, so 102 photos take about as long as
# the slowest few instead of all of them in a row.
#
# Runs automatically in the background on server startup when copies are missing. To rebuild
# everything from scratch, run from the backend/ folder:
#     python main.py

SOURCE_DIR = DATA_DIR / "products"
DISPLAY_DIR = DATA_DIR / "products_display"
BLACK_BORDER = 40  # border brightness below this counts as a black backdrop
FILL_TOLERANCE = 18  # how far from pure black a backdrop pixel may be (JPEG noise)
WHITE = (255, 255, 255)
MARKER = (255, 0, 255)  # temporary flood-fill color; magenta never appears in the catalogue


def has_black_backdrop(img: Image.Image) -> bool:
    a = np.asarray(img)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    return float(np.median(border)) < BLACK_BORDER


def whiten_backdrop(img: Image.Image) -> Image.Image:
    """Replace the black backdrop connected to the image edge with white."""
    out = img.copy()
    w, h = out.size
    # Seed the fill from points all around the border, so every edge-touching backdrop region is caught.
    step = max(1, min(w, h) // 40)
    seeds = [(x, y) for x in range(0, w, step) for y in (0, h - 1)] + [(x, y) for y in range(0, h, step) for x in (0, w - 1)]
    for xy in seeds:
        if max(out.getpixel(xy)) <= FILL_TOLERANCE:
            ImageDraw.floodfill(out, xy, MARKER, thresh=FILL_TOLERANCE)

    a = np.asarray(out).copy()
    backdrop = np.all(a == MARKER, axis=-1)
    a[backdrop] = WHITE

    # Soften the dark fringe that JPEG left around the garment edge: pixels right next to
    # the backdrop that are still almost black are blended toward white.
    near = np.asarray(Image.fromarray(backdrop.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    fringe = near & ~backdrop & (a.max(axis=-1) < 45)
    a[fringe] = (a[fringe] * 0.35 + np.array(WHITE) * 0.65).astype(np.uint8)
    return Image.fromarray(a)


def process_one(src: Path, force: bool = False) -> str:
    """Write one display copy. Runs in a worker process. Returns 'whitened', 'checked' or 'skipped'."""
    dest = DISPLAY_DIR / src.name
    if dest.exists() and not force:
        return "skipped"
    img = Image.open(src).convert("RGB")
    # Always fill: only near-black pixels connected to the border change, so photos that
    # already have a light backdrop are untouched apart from any black edge bars.
    whiten_backdrop(img).save(dest, quality=90)
    return "whitened" if has_black_backdrop(img) else "checked"


def prepare_all(force: bool = False, workers: int | None = None) -> tuple[int, int]:
    """Write a display copy of every product photo, in parallel. Returns (whitened, checked).

    workers=1 runs them one at a time (used to measure the speed-up).
    """
    DISPLAY_DIR.mkdir(exist_ok=True)
    sources = sorted(SOURCE_DIR.glob("*.jpg"))
    workers = workers or os.cpu_count() or 1
    if workers == 1:
        results = [process_one(src, force) for src in sources]
    else:
        # Each photo is independent CPU-bound work, so separate processes (not threads) run them truly at once.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(process_one, sources, [force] * len(sources)))
    return results.count("whitened"), results.count("checked")


# ---------- Print artwork for the lookbook models (Problem 10) ----------
# The chest print of a real product, cut out as a transparent PNG, so it can be laid onto a
# model photo wearing a plain garment of the same color. Regions are rough fractions of the
# product photo (left, top, right, bottom); the exact print is found inside them.
PRINTS_DIR = DISPLAY_DIR / "prints"
PRINTS = {
    # product_id: (region, mode, threshold)
    #   mode "light": white ink on a dark garment (alpha from how much brighter than the fabric)
    #   mode "ink":   colored ink on heathered gray (alpha from color distance, high threshold
    #                 so the heather texture stays transparent)
    "basic-hoodie-big-yale": ((0.30, 0.42, 0.76, 0.57), "light", 60),
    "baseball-left-chest-crewneck": ((0.52, 0.18, 0.735, 0.31), "light", 60),
    "benjamin-franklin-1-4-zip": ((0.54, 0.20, 0.69, 0.335), "ink", 55),
    "super-heavyweight-crewneck-arched-yale-crest": ((0.335, 0.29, 0.58, 0.598), "ink", 60),
    "champion-reverse-weave-crewneck": ((0.27, 0.17, 0.68, 0.345), "ink", 60),
}


def extract_print(product_id: str, region: tuple[float, float, float, float], mode: str, threshold: float) -> Image.Image:
    """Cut the print out of a product photo, leaving the fabric transparent."""
    img = Image.open(SOURCE_DIR / f"{product_id}.jpg").convert("RGB")
    w, h = img.size
    box = (int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h))
    a = np.asarray(img.crop(box)).astype(float)
    # Fabric color = median of the region's border, which is plain garment.
    border = np.concatenate([a[:3].reshape(-1, 3), a[-3:].reshape(-1, 3), a[:, :3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    base = np.median(border, axis=0)
    if mode == "light":
        diff = a.mean(axis=-1) - base.mean()  # only brighter-than-fabric pixels count
    else:
        diff = np.sqrt(((a - base) ** 2).sum(axis=-1))
    alpha = np.clip((diff - threshold) / 40, 0, 1)  # soft edge between fabric and ink
    if mode == "ink":
        # Drop scattered specks of heather texture: keep ink only where the area around it is mostly ink.
        density = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))) / 255
        alpha = alpha * (density > 0.18)
    ys, xs = np.where(alpha > 0.5)
    if len(xs) == 0:
        raise ValueError(f"No print found for {product_id}")
    pad = 3
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad)
    rgb = a if mode != "light" else np.full_like(a, 245)  # white ink prints as clean off-white
    rgba = np.dstack([rgb, alpha * 255])[y0:y1, x0:x1].astype(np.uint8)
    return Image.fromarray(rgba, "RGBA").filter(ImageFilter.MedianFilter(3)) if mode == "ink" else Image.fromarray(rgba, "RGBA")


def prepare_prints(force: bool = False) -> int:
    PRINTS_DIR.mkdir(parents=True, exist_ok=True)
    made = 0
    for product_id, spec in PRINTS.items():
        dest = PRINTS_DIR / f"{product_id}.png"
        if dest.exists() and not force:
            continue
        extract_print(product_id, *spec).save(dest)
        made += 1
    return made


def ensure_display_images() -> None:
    """Called on server startup: build any missing display copies."""
    missing = {p.name for p in SOURCE_DIR.glob("*.jpg")} - {p.name for p in DISPLAY_DIR.glob("*.jpg")}
    if missing:
        prepare_all()
    prepare_prints()


def _cli_prepare_images() -> None:
    start = time.perf_counter()
    whitened, checked = prepare_all(force=True)
    prepare_prints(force=True)
    print(
        f"White backdrop added to {whitened} photos; {checked} light photos checked for black edges "
        f"({time.perf_counter() - start:.1f}s with {os.cpu_count()} workers). Saved in {DISPLAY_DIR}"
    )


# ========================================================================================
# API
# ========================================================================================
# Products, images, chat and chat history.

log = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API")

# The Vite dev server runs on a different port, so allow it to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)  # the account routes above


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Plain-English validation errors that never echo the submitted values (like passwords)."""
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]).replace("_", " ")
        if err["type"] == "string_too_short" and field == "password":
            messages.append("Password must be at least 8 characters.")
        elif err["type"] == "string_too_short":
            messages.append(f"Please enter your {field}.")
        else:
            messages.append(f"Please check your {field}.")
    return JSONResponse(status_code=422, content={"detail": " ".join(dict.fromkeys(messages))})


# Product images: catalogue paths look like "products/<id>.jpg", served at /images/<id>.jpg.
# They're served from white-backed display copies (the Product photos section above), so dark garments are
# never shown on a black backdrop. Missing copies are built in parallel in a background
# thread at startup, so the server never waits; until a copy exists, the original is served.
ORIGINAL_IMAGES = DATA_DIR / "products"
IMAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*\.jpg$")


@app.on_event("startup")
def build_display_images() -> None:
    def run() -> None:
        try:
            ensure_display_images()
        except Exception:
            log.exception("Couldn't prepare display images; originals will be served")

    threading.Thread(target=run, name="prepare-images", daemon=True).start()


@app.get("/images/prints/{name}")
def print_artwork(name: str) -> FileResponse:
    """Product print artwork (transparent PNG) for the lookbook models; see PRINTS above."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.png", name):
        raise HTTPException(404, "Print not found")
    path = DISPLAY_DIR / "prints" / name
    if not path.is_file():
        raise HTTPException(404, "Print not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/images/{name}")
def product_image(name: str) -> FileResponse:
    if not IMAGE_NAME.match(name):  # only plain product file names, so no path tricks like ../
        raise HTTPException(404, "Image not found")
    for folder in (DISPLAY_DIR, ORIGINAL_IMAGES):
        path = folder / name
        if path.is_file():
            return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404, "Image not found")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- Products ----------

@app.get("/api/products")
def list_products(
    q: str = "",
    garment_type: str | None = None,
    color: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = False,
) -> list[ProductDetail]:
    """Every product, or, with any filter, the same search the agent uses (best match first).

    The chat's "See all" link passes the agent's own search here, so the page shows exactly
    what the agent found.
    """
    filters = SearchFilters(
        query=q, garment_type=garment_type, color=color, min_price=min_price,
        max_price=max_price, size=size, in_stock_only=in_stock_only,
    )
    products = load_all_products()
    if filters == SearchFilters():
        return products
    by_id = {p.product_id: p for p in products}
    return [by_id[p.product_id] for p in search_with(filters, limit=len(by_id)).matches]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> ProductDetail:
    product = load_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------- Chat ----------

def save_chat(user_id: int, user_text: str, reply: ChatResponse) -> None:
    """Keep a signed-in shopper's conversation, including the product matches shown.

    products_json holds {"title", "search", "product_ids"}; cards are rebuilt on reload.
    """
    user_text, _ = redact_sensitive(user_text)  # safety rule 1: never store card numbers or SSNs
    products_json = None
    if reply.matches:
        products_json = json.dumps({
            "title": reply.matches.title,
            "search": reply.matches.search.model_dump() if reply.matches.search else None,
            "product_ids": [p.product_id for p in reply.matches.products],
        })
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user_id, user_text)
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply.content, products_json),
        )


MEMORY_TURNS = 20  # how many saved messages the agent sees as memory


def load_memory(user_id: int, limit: int = MEMORY_TURNS) -> list[ChatTurn]:
    """A signed-in shopper's most recent saved messages, oldest first: the agent's memory."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [ChatTurn(role=r["role"], content=r["content"][:4000]) for r in reversed(rows)]


def chat_inputs(body: ChatRequest, request: Request) -> tuple[dict | None, CustomerProfile, list[ChatTurn], str]:
    """Who is chatting, their history and their new message (shared by both chat endpoints)."""
    user = current_user(request)
    latest = body.messages[-1]
    if latest.role != "user":
        raise HTTPException(400, "The last message must be from the shopper.")
    if user:
        # Signed in: who they are comes from the session cookie, and their history from the
        # database, so it survives reloads and new devices and can't be faked by the browser.
        customer = CustomerProfile(
            signed_in=True, first_name=user["first_name"], last_name=user["last_name"], email=user["email"]
        )
        history = load_memory(user["id"])
    else:
        # Guest: chat works, but the only memory is what the browser sends for this visit.
        customer = CustomerProfile(signed_in=False)
        history = body.messages[:-1]
    return user, customer, history, latest.content


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Plain JSON chat: the whole reply at once."""
    user, customer, history, message = chat_inputs(body, request)
    try:
        reply = await run_chat(history, message, customer, body.page)
    except Exception:
        log.exception("Chat agent failed")
        raise HTTPException(503, "Sorry, our assistant is having trouble right now. Please try again in a moment.")
    if user:
        save_chat(user["id"], message, reply)
    return reply


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """Streaming chat (Problem 9): one JSON event per line (NDJSON) as the agent works.
    See agent.stream_chat for the event types. The website uses this endpoint."""
    user, customer, history, message = chat_inputs(body, request)

    async def events():
        async for event in stream_chat(history, message, customer, body.page):
            if event["type"] == "done" and user:
                save_chat(user["id"], message, ChatResponse.model_validate(event["message"]))
            yield json.dumps(event) + "\n"

    # no-cache / no buffering so each line reaches the browser immediately
    return StreamingResponse(
        events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def saved_matches(products_json: str | None):
    """Rebuild a saved reply's matches. Handles our {title, search, product_ids} format and the
    seed data's older list of product objects."""
    saved = json.loads(products_json or "null")
    if isinstance(saved, dict):
        search = saved.get("search")
        return matches_for(saved.get("product_ids", []), saved.get("title"), SearchFilters(**search) if search else None)
    if isinstance(saved, list):
        return matches_for([p["product_id"] for p in saved if isinstance(p, dict) and "product_id" in p], None)
    return None


@app.get("/api/chat/history")
def chat_history(request: Request) -> list[dict]:
    """The signed-in shopper's saved chat (last 50 messages), oldest first. Empty when signed out.

    Product cards are rebuilt from the saved product IDs, so they show today's price and stock.
    """
    user = current_user(request)
    if user is None:
        return []
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT 50",
            (user["id"],),
        ).fetchall()
    history = []
    for r in reversed(rows):
        history.append({"role": r["role"], "content": r["content"], "matches": saved_matches(r["products_json"])})
    return history


@app.delete("/api/chat/history")
def clear_chat_history(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user["id"],))
    return {"ok": True}


if __name__ == "__main__":
    # Rebuild every display photo and print from scratch:  python main.py
    _cli_prepare_images()
