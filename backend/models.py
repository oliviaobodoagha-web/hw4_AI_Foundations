"""Structured types shared by the API, the agent and its tools (Problem 5)."""

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Products (what tools return to the agent, and what the website shows) ----------

class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductSummary(BaseModel):
    """One product as a search result or chat card. All values come straight from the database.

    price is in US dollars. Each product comes in one colorway; the only options are sizes.
    """

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str] = Field(
        description=(
            "Colors that appear on this ONE item (e.g. a navy hoodie with white lettering is "
            "['navy blue', 'white']). These are NOT separate color options to choose from."
        )
    )
    image_url: str
    total_stock: int = Field(description="Units in stock across all sizes; 0 means sold out everywhere")
    sizes_in_stock: list[str] = Field(description="Sizes with at least one unit, in XS→XXL order")


class ProductDetail(ProductSummary):
    description: str
    search_tags: list[str]
    sizes: list[SizeStock] = Field(description="Every size with its exact quantity, including zeros")


class SearchFilters(BaseModel):
    """The exact search the agent ran, so the website can repeat it for 'See all'."""

    query: str = ""
    garment_type: str | None = None
    color: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    size: str | None = None
    in_stock_only: bool = False


class SearchResults(BaseModel):
    total_found: int = Field(description="How many catalogue items match in total; `matches` may show fewer")
    matches: list[ProductSummary] = Field(description="Best matches first (up to 12)")
    sold_out_in_requested_size: list[ProductSummary] = Field(
        default_factory=list,
        description="Items that match everything except they're sold out in the requested size. They exist!",
    )
    hint: str | None = Field(default=None, description="What to do next when nothing matched (hunger rule H3)")


StockStatus = Literal["in stock", "low stock", "sold out"]


class SizeStatus(BaseModel):
    size: str
    quantity: int
    status: StockStatus = Field(description="'sold out' = 0, 'low stock' = 1-3, 'in stock' = 4 or more")


class StockReport(BaseModel):
    """The honest answer to 'how many do you have?', for one size or all of them. Straight from the inventory table."""

    product_id: str
    name: str
    price: float
    requested_size: str | None = Field(description="The size asked about, or null when reporting every size")
    requested_quantity: int | None = Field(description="Units in the requested size (0 = sold out)")
    requested_status: StockStatus | None
    sizes: list[SizeStatus] = Field(description="Every size, XS→XXL, with its exact quantity")
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]
    summary: str = Field(description="Plain-English stock summary you can relay to the shopper")


# ---------- Agent context: who is chatting and what page they're on (Problem 8) ----------

class CustomerProfile(BaseModel):
    """Who is chatting. Filled in by the server from the session cookie, never from the browser."""

    signed_in: bool
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class PageContext(BaseModel):
    """Where the shopper is on the website, sent by the chat widget with each message."""

    path: str = Field(default="/", max_length=200, description="The page's path, e.g. /products/basic-hoodie-big-yale")
    product_id: str | None = Field(
        default=None, max_length=100, description="The product on screen, when the shopper is on a single-item page"
    )


# ---------- The agent's final answer ----------

MAX_MATCHES = 12  # most product cards one reply can put on the page
IMAGE_VERSION = "2"  # bump when product photo processing changes, so browsers fetch the new copies


class ShopReply(BaseModel):
    """The agent's structured answer: its message plus the product matches to show on the page.

    The agent only picks product IDs. Python looks them up, so it can't invent a product,
    price or picture.
    """

    reply: str = Field(description="Your message to the shopper, in friendly plain text or light Markdown")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_MATCHES,
        description=(
            "product_id values (copied exactly from tool results) of the items to show as product "
            "cards on the website, best match first. Empty if no products are relevant."
        ),
    )
    results_title: str | None = Field(
        default=None,
        max_length=60,
        description="Short heading for the cards on the page, e.g. 'Hoodies' or 'Navy crewnecks under $60'",
    )


# ---------- Chat API (the contract between FastAPI and the website) ----------

class ProductCard(ProductSummary):
    """One card on the website: image, name, price, short info and stock."""

    short_description: str = Field(description="First sentence of the catalogue description, max ~120 characters")


class ProductMatches(BaseModel):
    """The structured product matches for one chat reply. The website renders these as cards."""

    title: str = Field(description="Heading shown above the cards")
    search: SearchFilters | None = Field(
        default=None, description="The agent's search behind these cards, repeated by the 'See all' link"
    )
    total_found: int | None = Field(
        default=None, description="How many catalogue items that search matched in all (for 'See all N')"
    )
    products: list[ProductCard] = Field(description="Real products from the database, best match first")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(
        min_length=1,
        max_length=50,
        description=(
            "The conversation so far, newest last. Guests' history comes from here; for signed-in "
            "shoppers only the newest message is used and the history is loaded from the database."
        ),
    )
    page: PageContext | None = Field(default=None, description="The page the shopper is on")


class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    matches: ProductMatches | None = Field(default=None, description="Product cards to show, or null for none")


# ---------- Audit trail (Problem 12) ----------

class AuditEntry(BaseModel):
    """One step of one agent run, appended to output/audit_trail.json (never wiped)."""

    run_id: str = Field(description="Groups every step of one chat turn")
    timestamp: str = Field(description="When the step happened (UTC, ISO 8601)")
    step: Literal["request", "tool_call", "tool_result", "retry", "finished"]
    customer: Literal["guest", "signed_in"] = Field(description="Never a name or email")
    page: str | None = Field(default=None, description="The page the shopper was on")
    model: str | None = None
    tool_name: str | None = None
    args: str | None = Field(default=None, description="Short form of the tool arguments")
    result: str | None = Field(default=None, description="Short form of what came back")
    stop_reason: str | None = Field(
        default=None,
        description="On 'finished': completed, unverified_fallback, request_limit, tool_limit, time_limit, cancelled or error",
    )
    duration_ms: int | None = None
