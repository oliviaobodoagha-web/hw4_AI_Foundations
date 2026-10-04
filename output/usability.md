# Campus Customs: Usability Improvements

After the core shop worked (browsing, accounts, the chatbot, product cards from chat, and
customer memory), I added **two front-end improvements** and **two back-end
improvements**. Each one below says what I added and why it helps Campus Customs shoppers
or the business.

| # | Improvement | Type | Where to see it |
|---|---|---|---|
| F1 | Product carousel + 12-per-page grid with page numbers | Front end | Home page and Products page |
| F2 | Dark products never shown on a black background | Front end | Every product image |
| B1 | Streaming chat replies with live progress | Back end | The 💬 chat (bottom right) |
| B2 | Product images processed in parallel | Back end | `backend/prepare_images.py`, server startup |

---

## Front-end improvements

### F1. Product carousel + 12-per-page grid with page numbers

**1. What I added**
- A **carousel at the top** of the Products page ("Featured picks") and the Home page
  ("Fan favorites") that shows **3 products at a time**. The ‹ › arrows move to the next 3,
  and the dots show which set you're on.
  - The carousel features 12 varied products that are in stock in every size.
  - It shows 2 cards on tablets and 1 on phones so cards don't get too small.
- Under the carousel on the Products page, **all products 12 at a time (3 rows × 4)** with
  numbered pages: **‹ Prev 1 2 3 … 9 Next ›**, plus "Showing 25–36 of 102 items". The page
  number is kept in the URL (`/products?page=3`), so Back and refresh keep your place.
- **Compact carousel cards** and a **slimmer Home banner**, so the whole carousel fits on
  screen without scrolling. Before, the cards had extra white space under the description
  and ran past the bottom of the screen.

**2. Why it helps**
- **Shoppers** see products the moment the page loads instead of scrolling past a big
  banner or a 102-item wall. Twelve per page is easy to scan, and page numbers show how
  much is left and let shoppers jump around.
- **The business** gets to choose which products shoppers see first. The carousel puts
  well-stocked, varied items up front, the products Campus Customs can actually sell
  right now, which helps sales and avoids featuring sold-out sizes.

---

### F2. Dark products never shown on a black background

**1. What I added**
- 73 of the 102 provided product photos have a **pure-black background built into the
  image file**, and some light photos have black bars down the sides. Navy hoodies and
  dark tees almost disappeared against it.
- `backend/prepare_images.py` makes a **white-backed copy** of every photo. It fills in
  only the black area connected to the photo's edges, so the garment and any black
  lettering or logos on it stay as they are. The site serves these copies everywhere
  (grid, carousel, chat cards, product pages).
- The original photos in `data/products/` are **never changed**.

**2. Why it helps**
- **Shoppers** can actually see what they're buying: the color, the print and the details
  of dark items, which are most of the catalogue (navy is Yale's color). Clear photos mean
  more confident purchases and fewer "it looked different online" returns.
- **The business** gets a consistent, clean, professional look across the whole store, so
  every product looks like it belongs on the same official site, without anyone having
  to re-shoot or hand-edit 73 photos.

---

## Back-end improvements

### B1. Streaming chat replies with live progress

**1. What I added**
- A new streaming chat endpoint, **`POST /api/chat/stream`**. Instead of waiting for the
  whole answer, the server sends updates the moment they happen:
  1. **What the assistant is doing**, with a spinner: e.g. "Searching the catalogue…",
     "Checking live stock…", "Writing your answer…". The steps depend on the question:
     on a product page the assistant already knows which item "this" is, so it can skip
     searching and go straight to "Checking live stock…";
  2. **The reply text as it's written** (shown slightly faded as a draft);
  3. **The final, fact-checked answer** and the product cards.
- **Safety kept:** the fact check that blocks made-up prices and stock numbers still
  checks the finished answer. If it fails, the draft is withdrawn ("Double-checking
  against our inventory…") and the corrected answer replaces it, so an unchecked number
  is never left on screen.
- **Measured** (live, on the Champion Reverse Weave Hoodie 1 page, asking "is this
  available in XL?"):

  | Time | What the shopper sees |
  |---|---|
  | 2.00s | ⟳ "Checking live stock…" |
  | 3.62s | ⟳ "Writing your answer…" |
  | 3.82s | The first words of the reply ("Sorry…"); the rest streams in 40 small pieces |
  | 3.93s | The final, fact-checked answer: sold out in XL, in stock in S (25), M (20), L (20), XXL (15) |

  Before this improvement the chat showed nothing at all until the complete answer
  arrived.

**2. Why it helps**
- **Shoppers** see the assistant working within about 2–3 seconds instead of staring at a
  silent chat for 5–7 seconds. That makes it feel faster and more trustworthy ("Checking
  live stock…" shows the answer comes from real inventory), so they're less likely to
  give up and leave.
- **The business:** a chat that feels responsive gets used more, and shoppers who chat
  find products and buy. The live steps also make it visible that answers come from
  Campus Customs' real stock, not guesses, which builds trust in the brand.

---

### B2. Product images processed in parallel

**1. What I added**
- `backend/prepare_images.py` (which makes the white-backed photos from F2) now processes
  photos **in parallel, one worker per CPU core** (Python `ProcessPoolExecutor`), instead
  of one photo after another.
- Measured on a 12-core Mac, all 102 photos (two separate runs):

  | Workers | Run 1 | Run 2 | Speed-up |
  |---|---|---|---|
  | 1 (one at a time) | 8.68s | 9.0s | — |
  | 4 | 2.50s | — | ~3.5× |
  | 12 (one per core) | **1.31s** | **1.4s** | **~6.5×** |

- **The server never waits on it:** at startup, any missing photos are built in the
  background. Until a white-backed copy exists, the original photo is shown (never a
  broken image).
- The image address only accepts plain product file names, so requests that try to reach
  other files (like `/images/../../.env`) are refused.

**2. Why it helps**
- **The business:** new or updated product photos (new merch, a new season, a Game-day
  drop) are ready about 6.5× faster. It scales with the catalogue: hundreds of new photos
  take seconds, not minutes. Because it runs in the background, the store is never down
  or slow while photos are processed.
- **Shoppers** never see a missing or broken product image, even right after new photos
  are added. They get the original until the cleaned-up version is ready.

---

*Technical details for all four improvements are in `output/harness.md`, sections 6b
(front end) and 6c (back end).*
