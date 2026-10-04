"""Accounts: password hashing, sign-up, log-in, and signed session cookies (Problem 4).

Passwords are never stored. Each user row keeps only a salted PBKDF2-SHA256 hash:

    seed accounts: pbkdf2_sha256$<salt>$<hex digest>                 (120,000 iterations)
    new accounts:  pbkdf2_sha256$<iterations>$<salt>$<hex digest>    (600,000 iterations)

Both formats are accepted at log-in, so the provided accounts keep working.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

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
