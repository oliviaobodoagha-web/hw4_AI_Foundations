"""Tools the shop agent can call, plus the product database helpers they share with main.py.

Every price, size and stock number the agent mentions has to come from one of these
tools. They open the database read-only, so the agent can never change it.

Problem 6: each tool also records the facts it returned in ShopDeps, and fact_check()
compares the agent's reply against them, so a price or quantity that didn't come from
the database is caught before the shopper sees it.
"""

import functools
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import ModelRetry, RunContext

from models import (
    IMAGE_VERSION,
    MAX_MATCHES,
    CustomerProfile,
    PageContext,
    ProductCard,
    ProductDetail,
    ProductMatches,
    ProductSummary,
    SearchFilters,
    SearchResults,
    SizeStatus,
    SizeStock,
    StockReport,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
MAX_RESULTS = MAX_MATCHES  # search hits the agent sees per call
LOW_STOCK = 3  # 1-3 units left counts as "low stock"


@dataclass
class ShopDeps:
    """The agent's context for one chat turn, handed to every tool and dynamic instruction.

    - customer: who is chatting (Problem 8), from the server-side session, never the browser.
    - page / viewed_product: where they are on the site, so "this" can mean the item on screen.
    - seen_*: every price, quantity and product ID the tools returned this turn (Problem 6 fact check).
    """

    customer: CustomerProfile = field(default_factory=lambda: CustomerProfile(signed_in=False))
    page: PageContext | None = None
    viewed_product: ProductDetail | None = None  # looked up from page.product_id in the database
    shopper_numbers: set[float] = field(default_factory=set)  # numbers the shopper typed, e.g. "under $60"
    seen_prices: set[float] = field(default_factory=set)
    seen_quantities: set[int] = field(default_factory=set)
    seen_product_ids: set[str] = field(default_factory=set)
    sensitive_removed: list[str] = field(default_factory=list)  # e.g. ["card number"] masked from this message
    asked_sizes: set[str] = field(default_factory=set)  # sizes the shopper mentioned this turn (hunger rule H2)
    stock_checked: bool = False  # did a stock tool run this turn? (hunger rule H2)
    tool_calls: set[str] = field(default_factory=set)  # tool + args already called this turn (satiation rule S2)
    last_search: SearchFilters | None = None  # the agent's most recent search_products call
    last_search_total: int | None = None

    def record(self, product: ProductSummary) -> None:
        self.seen_prices.add(round(product.price, 2))
        self.seen_quantities.add(product.total_stock)
        self.seen_product_ids.add(product.product_id)
        if isinstance(product, ProductDetail):
            self.seen_quantities.update(s.quantity for s in product.sizes)


def build_deps(
    customer: CustomerProfile,
    page: PageContext | None,
    shopper_numbers: set[float],
    sensitive_removed: list[str] | None = None,
) -> ShopDeps:
    """Assemble the agent context for one turn. The viewed product is looked up in the database,
    so the browser can only say *which* product is on screen, never what it costs or holds."""
    viewed = load_product(page.product_id) if page and page.product_id else None
    deps = ShopDeps(
        customer=customer, page=page, viewed_product=viewed, shopper_numbers=shopper_numbers,
        sensitive_removed=sensitive_removed or [],
    )
    if viewed:
        deps.record(viewed)  # its price and stock came from the database, so they may be quoted
    return deps


# ---------- Database helpers ----------

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _size_key(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)


def _stock_by_product(conn: sqlite3.Connection) -> dict[str, list[SizeStock]]:
    stock: dict[str, list[SizeStock]] = {}
    for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
        stock.setdefault(r["product_id"], []).append(SizeStock(size=r["size"], quantity=r["quantity"]))
    for sizes in stock.values():
        sizes.sort(key=lambda s: _size_key(s.size))
    return stock


def _detail(row: sqlite3.Row, sizes: list[SizeStock]) -> ProductDetail:
    return ProductDetail(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        image_url=f"/images/{Path(row['image_file_path']).name}?v={IMAGE_VERSION}",
        total_stock=sum(s.quantity for s in sizes),
        sizes_in_stock=[s.size for s in sizes if s.quantity > 0],
        description=row["description"],
        search_tags=json.loads(row["search_tags"]),
        sizes=sizes,
    )


def load_all_products() -> list[ProductDetail]:
    with connect() as conn:
        stock = _stock_by_product(conn)
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
    return [_detail(r, stock.get(r["product_id"], [])) for r in rows]


def load_product(product_id: str) -> ProductDetail | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return None
        sizes = [
            SizeStock(size=r["size"], quantity=r["quantity"])
            for r in conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,))
        ]
    sizes.sort(key=lambda s: _size_key(s.size))
    return _detail(row, sizes)


def short_description(text: str, limit: int = 120) -> str:
    """First sentence of a description, trimmed to fit on a card."""
    first = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    if len(first) <= limit:
        return first
    return first[: first.rfind(" ", 0, limit)].rstrip(",;:") + "…"


def cards_for(product_ids: list[str]) -> list[ProductCard]:
    """Real product cards for the IDs the agent picked, in its order. Unknown IDs are dropped."""
    by_id = {p.product_id: p for p in load_all_products()}
    cards: list[ProductCard] = []
    for pid in dict.fromkeys(product_ids):  # de-duplicate, keep order
        if pid in by_id:
            p = by_id[pid]
            cards.append(ProductCard(**_summary(p).model_dump(), short_description=short_description(p.description)))
    return cards[:MAX_MATCHES]


def matches_for(
    product_ids: list[str],
    title: str | None,
    filters: SearchFilters | None = None,
    total_found: int | None = None,
) -> ProductMatches | None:
    """The structured matches the website renders, or None when there are no real products."""
    cards = cards_for(product_ids)
    if not cards:
        return None
    if filters is not None and total_found is None:
        total_found = search_with(filters, limit=10_000).total_found
    return ProductMatches(
        title=(title or "Picks from our chat").strip(), search=filters, total_found=total_found, products=cards
    )


def search_with(filters: SearchFilters, limit: int = MAX_RESULTS) -> SearchResults:
    return search(**filters.model_dump(), limit=limit)


# ---------- Search ----------

# Shoppers' words → the words the catalogue uses. garment_type is messy (22 variants).
SYNONYMS = {
    "tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "tshirts": "t-shirt",
    "hoodies": "hoodie", "hooded": "hoodie", "hoody": "hoodie",
    "sweatshirts": "sweatshirt", "sweater": "sweatshirt", "sweaters": "sweatshirt", "crew": "crewneck",
    "crewnecks": "crewneck", "quarterzip": "quarter-zip", "1/4": "quarter-zip", "zip": "zip",
    "jackets": "jacket", "coat": "jacket", "fleeces": "fleece",
    "grey": "gray",
}
STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "do", "you", "have", "any", "some",
    "i", "me", "my", "want", "need", "looking", "show", "something", "that", "is", "are", "it", "on",
    "yale", "campus", "customs",  # on nearly every product, so they don't help rank
}


def _words(text: str) -> list[str]:
    text = text.lower().replace("t shirt", "tshirt").replace("t-shirts", "t-shirt").replace("quarter zip", "quarterzip")
    words = re.findall(r"[a-z0-9/\-]+", text)
    return [SYNONYMS.get(w, w) for w in words if w not in STOPWORDS]


def _matches(product: ProductDetail, word: str) -> int:
    """Weighted score for one search word; the name and tags count most."""
    score = 0
    if word in product.name.lower():
        score += 3
    if any(word in t.lower() for t in product.search_tags):
        score += 2
    if word in product.garment_type.lower():
        score += 2
    if any(word in c.lower() for c in product.colors):
        score += 2
    if word in product.description.lower():
        score += 1
    return score


def search(
    query: str = "",
    garment_type: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = False,
    limit: int = MAX_RESULTS,
) -> SearchResults:
    results: list[tuple[int, ProductDetail]] = []
    sold_out_in_size: list[tuple[int, ProductDetail]] = []
    words = _words(query)
    type_words = _words(garment_type or "")
    color_words = _words(color or "")
    size = size.upper().strip() if size else None

    for p in load_all_products():
        if max_price is not None and p.price > max_price:
            continue
        if min_price is not None and p.price < min_price:
            continue
        if type_words and not all(w in (p.garment_type + " " + p.name).lower() for w in type_words):
            continue
        if color_words and not all(any(w in c.lower() for c in p.colors) for w in color_words):
            continue
        if in_stock_only and p.total_stock == 0:
            continue
        score = sum(_matches(p, w) for w in words)
        if words and score == 0:
            continue
        # Don't silently drop an item just because the requested size is sold out.
        (sold_out_in_size if size and size not in p.sizes_in_stock else results).append((score, p))

    limit = max(1, limit)
    return SearchResults(
        total_found=len(results),
        matches=[_summary(p) for _, p in sorted(results, key=_rank)[:limit]],
        sold_out_in_requested_size=[_summary(p) for _, p in sorted(sold_out_in_size, key=_rank)[:limit]],
    )


def _rank(item: tuple[int, ProductDetail]) -> tuple[int, str]:
    return (-item[0], item[1].name)


def _summary(p: ProductDetail) -> ProductSummary:
    return ProductSummary(**p.model_dump(exclude={"description", "search_tags", "sizes"}))


# ---------- Guardrails on every tool (Problem 12) ----------

def guarded(tool):
    """Satiation rule S2: the same tool with the same arguments may run only once per turn.
    A repeat is sent back to the model ("use the earlier result and answer") instead of running again."""

    @functools.wraps(tool)
    def wrapper(ctx: RunContext[ShopDeps], *args, **kwargs):
        key = tool.__name__ + json.dumps([args, kwargs], sort_keys=True, default=str)
        if key in ctx.deps.tool_calls:
            raise ModelRetry(
                f"You already called {tool.__name__} with these exact arguments this turn. "
                "Use that earlier result and answer the shopper now; don't call it again."
            )
        ctx.deps.tool_calls.add(key)
        return tool(ctx, *args, **kwargs)

    return wrapper


SIZE_WORDS = {
    "xs": "XS", "x-small": "XS", "extra small": "XS", "s": "S", "small": "S", "m": "M", "medium": "M",
    "l": "L", "large": "L", "xl": "XL", "x-large": "XL", "extra large": "XL", "xxl": "XXL", "2xl": "XXL",
}
_SIZE_RE = re.compile(r"\b(xxl|2xl|xl|x-large|extra large|xs|x-small|extra small|small|medium|large|s|m|l)\b", re.I)


def sizes_mentioned(text: str) -> set[str]:
    """Sizes a shopper asked about. Single letters count only in phrases like "in M" / "size L" / "an XL"."""
    found = set()
    for m in _SIZE_RE.finditer(text):
        word = m.group(1).lower()
        if len(word) == 1:
            before = text[max(0, m.start() - 6):m.start()].lower()
            if not re.search(r"(in|size|an|a)\s+$", before):
                continue
        found.add(SIZE_WORDS[word])
    return found


STOCK_CLAIM_RE = re.compile(r"\b(in stock|sold out|available|left in|out of stock)\b", re.I)


# ---------- Agent tools ----------

def search_products(
    ctx: RunContext[ShopDeps],
    query: str = "",
    garment_type: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = False,
) -> SearchResults:
    """Search the Campus Customs catalogue. Use this for any request to find or recommend products.

    Args:
        query: Free-text keywords, e.g. "baseball crewneck", "Harvard Yale game", "bulldog".
        garment_type: Optional kind of item, e.g. "hoodie", "t-shirt", "crewneck", "quarter-zip", "jacket".
        color: Optional color the item must include, e.g. "navy", "gray", "white".
        max_price: Optional highest price in dollars.
        min_price: Optional lowest price in dollars.
        size: Optional size the shopper needs: XS, S, M, L, XL or XXL. Items in stock in that size
            go in `matches`; items that otherwise match but are sold out in that size go in
            `sold_out_in_requested_size` (they DO exist, so tell the shopper they're sold out in that size).
        in_stock_only: If true, skip items that are sold out in every size.

    Returns `total_found` (how many items match in all) and up to 12 `matches`, best first,
    with price, colors, total stock and sizes in stock. When total_found is bigger than the
    number of matches, say so (e.g. "We have 27 hoodies; here are 12 favorites").
    If both lists are empty, nothing in the catalogue matches. Say so; don't invent items.
    """
    results = search(query, garment_type, color, max_price, min_price, size, in_stock_only)
    for p in results.matches + results.sold_out_in_requested_size:
        ctx.deps.record(p)
    ctx.deps.last_search = SearchFilters(
        query=query, garment_type=garment_type, color=color, min_price=min_price,
        max_price=max_price, size=size, in_stock_only=in_stock_only,
    )
    ctx.deps.last_search_total = results.total_found
    filters_used = any([garment_type, color, max_price, min_price, size, in_stock_only])
    if results.total_found == 0 and not results.sold_out_in_requested_size:
        # Hunger rule H3: don't give up after one narrow search.
        results.hint = (
            "Nothing matched. Try ONE broader search (fewer filters or simpler keywords) before telling "
            "the shopper we don't carry it." if filters_used or len(query.split()) > 2
            else "Nothing matched even a simple search. Say honestly that we don't carry it and suggest close alternatives."
        )
    return results


def _require_product(product_id: str) -> ProductDetail:
    product = load_product(product_id.strip())
    if product is None:
        raise ModelRetry(f"No product has id '{product_id}'. Use search_products to find the right id.")
    return product


def get_product_details(ctx: RunContext[ShopDeps], product_id: str) -> ProductDetail:
    """The product's full description, exact price, colors, tags and stock for every size.

    Use this whenever the shopper asks what an item looks like, what it's made of / features,
    or what it costs. Quote the price exactly as returned.

    Args:
        product_id: The product_id from a search result, e.g. "basic-hoodie-big-yale".
    """
    product = _require_product(product_id)
    ctx.deps.record(product)
    ctx.deps.stock_checked = True
    return product


def _status(qty: int) -> str:
    return "sold out" if qty == 0 else "low stock" if qty <= LOW_STOCK else "in stock"


def check_stock(ctx: RunContext[ShopDeps], product_id: str, size: str | None = None) -> StockReport:
    """How many of a product are in stock, read live from the inventory table.

    Call this whenever the shopper asks about availability, sizes or "how many", and before
    saying an item is available in a size. Leave `size` empty to get every size.

    Args:
        product_id: The product_id from a search result.
        size: Optional single size to check: XS, S, M, L, XL or XXL.
    """
    product = _require_product(product_id)
    ctx.deps.record(product)
    ctx.deps.stock_checked = True

    requested = size.upper().strip() if size else None
    if requested is not None and requested not in SIZE_ORDER:
        raise ModelRetry(f"'{size}' isn't a size we carry. Sizes are: {', '.join(SIZE_ORDER)}.")

    sizes = [SizeStatus(size=s.size, quantity=s.quantity, status=_status(s.quantity)) for s in product.sizes]
    in_stock = [s.size for s in sizes if s.quantity > 0]
    sold_out = [s.size for s in sizes if s.quantity == 0]
    qty = next((s.quantity for s in sizes if s.size == requested), 0) if requested else None

    available = ", ".join(f"{s.size} ({s.quantity})" for s in sizes if s.quantity > 0) or "none"
    if requested is None:
        summary = f"{product.name}: in stock in {available}."
        if sold_out:
            summary += f" SOLD OUT in {', '.join(sold_out)}."
    elif qty == 0:
        summary = f"{product.name} is SOLD OUT in {requested}. Sizes still in stock: {available}."
    elif qty <= LOW_STOCK:
        summary = f"{product.name}: only {qty} left in {requested} (low stock)."
    else:
        summary = f"{product.name}: {qty} in stock in {requested}."

    return StockReport(
        product_id=product.product_id,
        name=product.name,
        price=product.price,
        requested_size=requested,
        requested_quantity=qty,
        requested_status=_status(qty) if qty is not None else None,
        sizes=sizes,
        sizes_in_stock=in_stock,
        sold_out_sizes=sold_out,
        summary=summary,
    )


# ---------- Fact check (Problem 6) ----------

PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
QUANTITY_RES = [
    re.compile(r"\b(\d{1,4})\s+(?:units?\s+|pieces?\s+)?(?:left|in stock|available|remaining)\b", re.I),
    re.compile(r"\bonly\s+(\d{1,4})\b", re.I),
    re.compile(r"\(\s*(\d{1,4})\s*\)(?![\s-]*\d)"),  # e.g. "M (15)", but not a phone area code "(475) 301-4205"
]
SHOPPER_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[float]:
    return {float(n) for n in SHOPPER_NUMBER_RE.findall(text.replace(",", ""))}


# ---------- Safety rules enforced in code (Problem 12) ----------

STORE_EMAIL = "orderdept@campuscustoms.com"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Rule 1: payment cards and Social Security numbers are never sent to the model or saved.
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    """The checksum every real card number passes; avoids flagging order numbers or phone numbers."""
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    """Mask card numbers and SSNs. Returns the safe text and what was removed."""
    found: list[str] = []

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.append("card number")
            return "[card number removed]"
        return m.group()

    text = CARD_RE.sub(card, text)
    if SSN_RE.search(text):
        found.append("Social Security number")
        text = SSN_RE.sub("[SSN removed]", text)
    return text, found


# Rule 3: no made-up discounts, free shipping, guarantees or restock dates.
PROMISE_RES = [
    re.compile(r"\b\d{1,2}\s?%\s?off\b", re.I),
    re.compile(r"\b(?:promo|coupon|discount)\s+code\b", re.I),
    re.compile(r"\bfree\s+(?:shipping|returns?|delivery|gift)\b", re.I),
    re.compile(r"\b(?:back in stock|restock(?:ed|ing)?)\b[^.!?]{0,40}\b(?:on|by|next|soon|tomorrow|this week|in \d+)\b", re.I),
    re.compile(r"\b(?:price match|price guarantee|on sale|sale price|clearance)\b", re.I),
    re.compile(r"\b(?:guarantee|promise)\s+(?:that|it|delivery|arrival)\b", re.I),
]
NEGATION_RE = re.compile(r"\b(?:no|not|don't|doesn't|isn't|aren't|can't|cannot|never|unable|without)\b|n't\b", re.I)


def promise_problems(reply: str) -> list[str]:
    problems = []
    for sentence in re.split(r"(?<=[.!?])\s+", reply):
        if NEGATION_RE.search(sentence):
            continue  # "we don't offer free shipping" is honest, not a promise
        for pattern in PROMISE_RES:
            m = pattern.search(sentence)
            if m:
                problems.append(f"'{m.group()}' is a discount or promise that is not in the store facts")
    return problems


def email_problems(reply: str, customer_email: str | None) -> list[str]:
    """Rule 2: the only emails the bot may show are the shopper's own and the store's order email."""
    allowed = {STORE_EMAIL, (customer_email or "").lower()}
    return [f"the email {e} must not be shared" for e in EMAIL_RE.findall(reply) if e.lower() not in allowed]


ALL_PRICE_RE = re.compile(r"\b(?:all|every|each)\b[^.!?$]{0,60}\$\s?(\d{1,4}(?:\.\d{1,2})?)", re.I)


def all_price_problems(reply: str, deps: ShopDeps) -> list[str]:
    """Honesty: "all priced at $58" must be true of every item the search found, not just most of them."""
    if deps.last_search is None:
        return []
    problems = []
    for raw in ALL_PRICE_RE.findall(reply):
        price = round(float(raw), 2)
        found = search_with(deps.last_search, limit=10_000)
        exceptions = [p for p in found.matches if round(p.price, 2) != price]
        if exceptions:
            ex = exceptions[0]
            problems.append(
                f"not every item is ${price:.2f}: {ex.name} is ${ex.price:.2f}"
                + (f" (and {len(exceptions) - 1} more)" if len(exceptions) > 1 else "")
                + "; say 'most' or give the real range"
            )
    return problems


def fact_check(reply: str, product_ids: list[str], deps: ShopDeps) -> list[str]:
    """Problems with a reply: invented prices, quantities or products (Problem 6), plus the code-enforced
    safety rules: no other people's emails (rule 2) and no made-up discounts or promises (rule 3)."""
    problems = email_problems(reply, deps.customer.email) + promise_problems(reply)
    problems += all_price_problems(reply, deps)
    # Hunger rule H2: a size-specific stock answer needs a stock lookup this turn, not a guess.
    if deps.asked_sizes and STOCK_CLAIM_RE.search(reply) and not deps.stock_checked:
        problems.append(
            f"you answered about size {', '.join(sorted(deps.asked_sizes))} without checking it; call check_stock first"
        )
    for raw in PRICE_RE.findall(reply):
        price = round(float(raw.replace(",", "")), 2)
        if price not in deps.seen_prices and price not in deps.shopper_numbers:
            problems.append(f"${raw} is not a price any tool returned this turn")
    for pattern in QUANTITY_RES:
        for raw in pattern.findall(reply):
            qty = int(raw)
            if qty not in deps.seen_quantities and qty not in deps.shopper_numbers:
                problems.append(f"the stock count {qty} did not come from a tool this turn")
    for pid in product_ids:
        if pid not in deps.seen_product_ids:
            problems.append(f"product_id '{pid}' was not returned by a tool this turn")
    return problems


def get_customer_profile(ctx: RunContext[ShopDeps]) -> CustomerProfile:
    """Who you're chatting with: signed in or a guest, and if signed in their first name,
    last name and email. Only ever about the current shopper; there is no way to look up anyone else."""
    return ctx.deps.customer


def get_viewed_product(ctx: RunContext[ShopDeps]) -> ProductDetail:
    """The product on the shopper's screen right now (description, price, colors, stock by size).

    Use this when they say "this", "it" or "this one" without naming an item.
    """
    if ctx.deps.viewed_product is None:
        path = ctx.deps.page.path if ctx.deps.page else "unknown"
        raise ModelRetry(
            f"The shopper isn't on a single-item page (they're on '{path}'). Ask which item they mean, "
            "or use search_products."
        )
    product = load_product(ctx.deps.viewed_product.product_id)  # re-read for live stock
    if product is None:
        raise ModelRetry("That product no longer exists. Ask which item they mean.")
    ctx.deps.record(product)
    ctx.deps.stock_checked = True
    return product


TOOLS = [guarded(t) for t in (search_products, get_product_details, check_stock, get_customer_profile, get_viewed_product)]
