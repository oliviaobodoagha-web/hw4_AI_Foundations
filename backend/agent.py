"""The Campus Customs shop agent: model, system prompt, tools and output type (Problem 5).

main.py calls stream_chat() for the website's streaming chat (Problem 9) and run_chat()
for the plain JSON endpoint.
"""

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from collections.abc import AsyncIterable, AsyncIterator
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits, capture_run_messages
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_core import from_json
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import AuditEntry, ChatResponse, ChatTurn, CustomerProfile, PageContext, ShopReply
from tools import TOOLS, ShopDeps, build_deps, fact_check, matches_for, numbers_in, redact_sensitive, sizes_mentioned

BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"

# The API key lives in a .env file, never in code: the repo's own .env (copied from .env.example),
# or else the nearest .env in a parent folder (e.g. the course project root).
for folder in [BACKEND_DIR.parent, *BACKEND_DIR.parent.parents]:
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")
        break

MODEL_NAME = os.getenv("CAMPUS_AGENT_MODEL", "gpt-5.6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

MAX_HISTORY_TURNS = 20  # older turns are dropped to keep each call small
MAX_MODEL_REQUESTS = 8  # caps tool-call loops so one message can't run up the bill
# Satiation guardrails (Problem 12): when the agent must stop.
MAX_TOOL_CALLS = 6  # S3: tool calls per turn (a normal answer uses 1-3)
TURN_TIMEOUT_S = 45  # S4: give up politely rather than keep the shopper waiting
MAX_REPLY_WORDS = 120  # S6: keep replies short
TIMEOUT_REPLY = "Sorry, that's taking longer than it should. Please try asking again in a moment."
TOO_BROAD_REPLY = (
    "That's a lot to look up at once! Try asking about a type of piece (like \"crewnecks under $60\") "
    "or a specific item, and I'll check its live price and stock."
)

# Shown if the agent still can't back its numbers with the database after its retries.
UNVERIFIED_REPLY = (
    "Sorry, I couldn't double-check that against our live inventory just now. "
    "Could you ask again, or open the item's page to see its current price and stock?"
)

log = logging.getLogger("campus_customs.agent")


# ---------- Audit trail (Problem 12) ----------
# Every step of every agent run is appended to output/audit_trail.json. The file is never
# wiped: new entries are added to the end, and a damaged file is moved aside, not deleted.

AUDIT_PATH = BACKEND_DIR.parent / "output" / "audit_trail.json"
AUDIT_TEXT_LIMIT = 200  # keep args/results short, so the audit stays readable
_audit_lock = threading.Lock()
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _short(value: object, limit: int = AUDIT_TEXT_LIMIT) -> str:
    """One readable line, with email addresses masked."""
    if hasattr(value, "model_dump"):  # tool results are Pydantic models: log them as compact JSON
        value = value.model_dump(mode="json", exclude={"sizes", "search_tags", "description"})
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = _EMAIL.sub("[email]", " ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _iso(ts: datetime | None = None) -> str:
    return (ts or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="milliseconds")


def append_audit(entries: list[AuditEntry]) -> None:
    """Append entries to the audit file. Thread-safe; never removes existing entries."""
    if not entries:
        return
    with _audit_lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if AUDIT_PATH.exists():
            try:
                existing = json.loads(AUDIT_PATH.read_text() or "[]")
                if not isinstance(existing, list):
                    raise ValueError("audit file is not a JSON list")
            except ValueError:
                # Never destroy history: keep the damaged file and start a fresh list beside it.
                AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.damaged-{int(time.time())}.json"))
                existing = []
        existing.extend(e.model_dump(exclude_none=True) for e in entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        tmp.replace(AUDIT_PATH)  # atomic swap, so a crash mid-write can't leave half a file


def audit_steps(run_id: str, base: dict, messages: list[ModelMessage]) -> list[AuditEntry]:
    """Turn the agent loop's messages into audit entries: tool calls, tool results and retries."""
    entries: list[AuditEntry] = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    entries.append(AuditEntry(
                        run_id=run_id, timestamp=_iso(msg.timestamp), step="tool_call", model=msg.model_name,
                        tool_name=part.tool_name, args=_short(part.args_as_dict()), **base,
                    ))
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    entries.append(AuditEntry(
                        run_id=run_id, timestamp=_iso(part.timestamp), step="tool_result",
                        tool_name=part.tool_name, result=_short(part.content), **base,
                    ))
                elif isinstance(part, RetryPromptPart):
                    # A tool error or a failed fact check sent back to the model to fix.
                    entries.append(AuditEntry(
                        run_id=run_id, timestamp=_iso(part.timestamp), step="retry",
                        tool_name=part.tool_name, result=_short(part.content), **base,
                    ))
    return entries


def build_model() -> OpenAIChatModel:
    """OpenAI-compatible model through the course Portkey gateway, using PORTKEY_API_KEY."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the project root .env file.")
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=api_key, timeout=60, max_retries=2)
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_agent() -> Agent[ShopDeps, ShopReply]:
    """Built on first use, so the API still starts (and serves products) without a key."""
    agent = Agent(
        build_model(),
        deps_type=ShopDeps,
        output_type=ShopReply,
        instructions=PROMPT_PATH.read_text(),
        tools=TOOLS,
        retries=2,
    )

    @agent.instructions
    def shopper_context(ctx: RunContext[ShopDeps]) -> str:
        """Re-written every turn from the agent context: who is chatting and what's on their screen."""
        return describe_context(ctx.deps)

    @agent.output_validator
    def only_database_facts(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        """Reject replies whose prices, stock counts or products didn't come from a tool this turn."""
        problems = fact_check(output.reply, output.product_ids, ctx.deps)
        # Satiation rule S6: short replies, at most one question back to the shopper.
        words = len(output.reply.split())
        if words > MAX_REPLY_WORDS:
            problems.append(f"the reply is {words} words; keep it under {MAX_REPLY_WORDS} (the cards show the details)")
        if output.reply.count("?") > 1:
            problems.append("ask the shopper at most one question")
        if problems:
            log.warning("Fact check failed: %s", "; ".join(problems))
            raise ModelRetry(
                "Your reply breaks the store's rules: "
                + "; ".join(problems)
                + ". Look facts up with the tools (search_products, get_product_details, check_stock) and quote "
                "only what they return; never share anyone else's email; and don't offer discounts, free "
                "shipping, sales, guarantees or restock dates. Remove anything you can't back up."
            )
        return brand_voice(output)

    return agent


# Guardrail G3: brand voice. No emojis, and no links except the store's own pages.
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F]")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_URL_RE = re.compile(r"https?://\S+")


def brand_voice(output: ShopReply) -> ShopReply:
    text = _EMOJI_RE.sub("", output.reply)
    text = _MD_LINK_RE.sub(r"\1", text)  # keep the link text, drop the outside URL
    text = _URL_RE.sub("", text)
    output.reply = re.sub(r"[ \t]{2,}", " ", text).strip()
    return output


def describe_context(deps: ShopDeps) -> str:
    """The 'current context' block added to the system prompt each turn (Problem 8)."""
    c = deps.customer
    lines = ["## Current context (from the website, this turn)"]
    if c.signed_in:
        lines.append(
            f"- Customer: signed in as {c.first_name} {c.last_name} ({c.email}). "
            "Their earlier conversations with you are included above, so you remember them."
        )
    else:
        lines.append("- Customer: a guest (not signed in). You don't know their name or email.")

    page = deps.page.path if deps.page else "unknown"
    lines.append(f"- Page: {page}")
    if deps.sensitive_removed:
        lines.append(
            f"- SAFETY: the shopper's message contained a {' and a '.join(deps.sensitive_removed)}, which was removed "
            "before you saw it and was not saved. Start your reply by kindly telling them never to share payment "
            "or ID numbers in chat: this shop can't take payments or orders here. Then help with the rest of the message."
        )
    if deps.viewed_product:
        p = deps.viewed_product
        lines.append(
            f'- They are viewing the product page for "{p.name}" (product_id: {p.product_id}). '
            '"This", "it" and "this one" mean this item unless they name another. '
            "Use get_viewed_product or check_stock for its details and stock."
        )
    return "\n".join(lines)


def to_history(turns: list[ChatTurn]) -> list[ModelMessage]:
    """The website's earlier chat turns, in PydanticAI's message format."""
    history: list[ModelMessage] = []
    for turn in turns[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return history


async def run_chat(
    history: list[ChatTurn],
    message: str,
    customer: CustomerProfile,
    page: PageContext | None = None,
    event_stream_handler=None,
) -> ChatResponse:
    """Answer the shopper's new message.

    history is the earlier conversation: from the database for signed-in shoppers, or from the
    browser for guests (main.py decides). customer and page become the agent's context (deps).
    event_stream_handler, if given, sees the agent's events live (used by stream_chat).
    """
    # Safety rule 1: card numbers and SSNs never reach the model, the audit trail or the database.
    message, removed = redact_sensitive(message)
    history = [ChatTurn(role=t.role, content=redact_sensitive(t.content)[0]) for t in history]
    # Numbers the shopper typed (budgets, sizes, quantities) may be repeated back.
    shopper_numbers = set().union(numbers_in(message), *(numbers_in(t.content) for t in history if t.role == "user"))
    deps: ShopDeps = build_deps(customer, page, shopper_numbers, removed)
    deps.asked_sizes = sizes_mentioned(message)  # hunger rule H2

    # Audit: one run_id ties together every step of this turn.
    run_id = uuid.uuid4().hex[:12]
    base = {"customer": "signed_in" if customer.signed_in else "guest", "page": page.path if page else None}
    started = time.perf_counter()
    prior = to_history(history)
    entries = [AuditEntry(run_id=run_id, timestamp=_iso(), step="request", model=MODEL_NAME, args=_short(message), **base)]

    def finish(stop_reason: str, result: str, messages: list[ModelMessage]) -> None:
        entries.extend(audit_steps(run_id, base, messages[len(prior):]))  # only this turn's steps
        entries.append(AuditEntry(
            run_id=run_id, timestamp=_iso(), step="finished", stop_reason=stop_reason, result=_short(result),
            duration_ms=round((time.perf_counter() - started) * 1000), **base,
        ))
        try:
            append_audit(entries)
        except OSError:
            log.exception("Could not write the audit trail")  # never break the chat over logging

    with capture_run_messages() as messages:
        try:
            result = await asyncio.wait_for(  # satiation rule S4: a hard time limit per turn
                get_agent().run(
                    message,
                    message_history=prior,
                    deps=deps,
                    # S3: at most 8 model calls and 6 tool calls per turn
                    usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS, tool_calls_limit=MAX_TOOL_CALLS),
                    event_stream_handler=event_stream_handler,
                ),
                timeout=TURN_TIMEOUT_S,
            )
        except UnexpectedModelBehavior:
            # Retries used up without a reply that passes the fact check: say so instead of guessing.
            log.exception("Agent could not produce a verified reply")
            finish("unverified_fallback", UNVERIFIED_REPLY, messages)
            return ChatResponse(content=UNVERIFIED_REPLY)
        except UsageLimitExceeded as exc:
            log.warning("Agent hit a usage limit: %s", exc)
            reason = "tool_limit" if "tool" in str(exc).lower() else "request_limit"
            reply_text = TOO_BROAD_REPLY if reason == "tool_limit" else UNVERIFIED_REPLY
            finish(reason, reply_text, messages)
            return ChatResponse(content=reply_text)
        except TimeoutError:
            log.warning("Agent turn timed out after %ss", TURN_TIMEOUT_S)
            finish("time_limit", TIMEOUT_REPLY, messages)
            return ChatResponse(content=TIMEOUT_REPLY)
        except asyncio.CancelledError:
            finish("cancelled", "shopper left before the answer finished", messages)
            raise
        except Exception as exc:
            finish("error", type(exc).__name__, messages)
            raise
    reply = result.output
    # The contract: look the chosen IDs up in the database, so every card is a real product.
    response = ChatResponse(
        content=reply.reply,
        # The search behind the cards is the agent's own last search, so counts always agree.
        matches=matches_for(reply.product_ids, reply.results_title, deps.last_search, deps.last_search_total),
    )
    cards = len(response.matches.products) if response.matches else 0
    finish("completed", f"{reply.reply} [cards: {cards}]", result.all_messages())
    return response


# ---------- Streaming (Problem 9, backend improvement 1) ----------

# What the shopper sees while each tool runs.
TOOL_STATUS = {
    "search_products": "Searching the catalogue…",
    "get_product_details": "Looking up product details…",
    "check_stock": "Checking live stock…",
    "get_viewed_product": "Looking at this item…",
    "get_customer_profile": "Checking your account…",
}
OUTPUT_TOOL = "final_result"  # PydanticAI's name for the structured-answer tool


def _partial_reply(args_json: str) -> str:
    """The `reply` text so far, from the half-written JSON of the agent's answer."""
    try:
        data = from_json(args_json, allow_partial="trailing-strings")
    except ValueError:
        return ""
    reply = data.get("reply") if isinstance(data, dict) else None
    return reply if isinstance(reply, str) else ""


async def stream_chat(
    history: list[ChatTurn],
    message: str,
    customer: CustomerProfile,
    page: PageContext | None = None,
) -> AsyncIterator[dict]:
    """Run the agent and yield events for the website as they happen:

      {"type": "status", "text": "Searching the catalogue…"}  a tool started
      {"type": "delta",  "text": "…"}                          more of the draft reply
      {"type": "reset"}                                        the draft failed the fact check; a new one follows
      {"type": "done",   "message": ChatResponse}              the final, fact-checked reply and product cards

    Draft text is shown as unverified until "done": the fact check (Problem 6) runs on the
    finished answer, and if it fails the draft is withdrawn ("reset") and rewritten.
    """
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    drafted = False  # has any draft text been shown yet? (spans the agent's model calls)

    async def on_events(ctx: RunContext[ShopDeps], events: AsyncIterable[AgentStreamEvent]) -> None:
        nonlocal drafted
        answer_json, sent = "", ""
        async for event in events:
            if isinstance(event, PartStartEvent) and isinstance(event.part, ToolCallPart):
                if event.part.tool_name == OUTPUT_TOOL:
                    if drafted:  # a second answer attempt: withdraw the first draft
                        await queue.put({"type": "reset"})
                        drafted = False
                    answer_json, sent = event.part.args_as_json_str() if event.part.args else "", ""
                    await queue.put({"type": "status", "text": "Writing your answer…"})
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ToolCallPartDelta):
                if isinstance(event.delta.args_delta, str):
                    answer_json += event.delta.args_delta
                    text = _partial_reply(answer_json)
                    if len(text) > len(sent) and text.startswith(sent):
                        await queue.put({"type": "delta", "text": text[len(sent):]})
                        sent, drafted = text, True
            elif isinstance(event, FunctionToolCallEvent):
                status = TOOL_STATUS.get(event.part.tool_name)
                if status:
                    await queue.put({"type": "status", "text": status})

    async def run() -> None:
        try:
            reply = await run_chat(history, message, customer, page, event_stream_handler=on_events)
            await queue.put({"type": "done", "message": reply.model_dump()})
        except Exception:
            log.exception("Streaming chat failed")
            await queue.put({"type": "error", "text": "Sorry, our assistant is having trouble right now. Please try again in a moment."})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while (item := await queue.get()) is not None:
            yield item
    finally:
        if not task.done():  # the shopper closed the page mid-answer
            task.cancel()
