"""Campus Customs API: the file Uvicorn runs.

Problem 3: products, stock by size, and product images from data/campus_customs.db.
Problem 4: accounts (sign-up, log-in, log-out), in auth.py.
Problem 5: the shop chatbot. POST /api/chat runs the PydanticAI agent (agent.py, tools.py,
models.py, prompts/prompt.md).
Problem 8: customer memory. Signed-in shoppers' chats are saved to chat_messages and the
agent's history is loaded from there; the agent also gets their profile and page context.

Run from the backend/ folder:
    cd backend && source .venv/bin/activate
    uvicorn main:app --reload --port 8000
"""

import json
import logging
import re
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from agent import run_chat, stream_chat
from auth import current_user, get_db
from prepare_images import DISPLAY_DIR, ensure_display_images
from auth import router as auth_router
from models import ChatRequest, ChatResponse, ChatTurn, CustomerProfile, ProductDetail, SearchFilters
from tools import DATA_DIR, load_all_products, load_product, matches_for, redact_sensitive, search_with

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

app.include_router(auth_router)


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
# They're served from white-backed display copies (prepare_images.py), so dark garments are
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
    """Product print artwork (transparent PNG) for the lookbook models; see prepare_images.PRINTS."""
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
