# Homework 4 — AI Prompts Log

This file logs the prompts I typed to my vibe coder (Claude) for Homework 4.
Each problem has its own section with the problem number and title, the prompts I typed, and any follow-up prompts along with what was missing.

---

## Setup — Creating the Prompt Log

**Prompt 1:**
> Great now create AI_prompts.md at the start of this assignment and keep it updated as I work. This file is the log of what I typed to your vibe coder. I will describe each problem to you the vibe coder in my own words. Put one section for each problem. Each section must include the following: 1. the problem number and title 2. At least one prompt that I typed, in my own words as much as possible 3. One follow up prompt if I needed it and a sentence on what was lacking if relevant. This is the first prompt — label AI_prompts.md accordingly.

**Follow-up prompt:** None needed.

---

## Problem 2 — Understanding the Database Fields

**Prompt 2:**
> Pull the data/campus_customs.db so that I can understand the fields.

**Follow-up prompt:**
> I need to understand each of these fields and its importance to the chatbot. Can you quickly list each table and field, summarize its importance, and add it in output/harness.md?

*What was lacking:* The first pull only showed what each field held. It didn't explain why each field matters to the chatbot, and it wasn't saved anywhere I could refer back to.

**Additional prompt (harness file):**
> Start a file called output/harness.md. When it's ready take me to it; if it already exists don't make a new one, just take me to it.

---

## Problem 3 — Scaffolding the Frontend (and a Starter API)

**Prompt 3:**
> Scaffold a React + Vite + TypeScript frontend for Campus Customs. Put a navigation bar at the top that links to the main pages: Home, Products, About Us, Log In, Create Account. Pull Campus Customs–style wording from yalebulldogblue.com for Home and About Us, but write these pages in my voice (do not copy the original site text). Next, on the Products page show product images from the catalogue (use the image paths in the database) with basic product info (name, price, short description). Make each product open a single-item page (large image on one side, full product text on the other: description, price, sizes/stock when you have them). Clicking a card on Products should take the shopper there. Add a chat interface in the bottom right of the site (a floating chat panel is fine). It does not need to talk to an agent yet; a stub that will call the backend later will suffice. I will also need a small API soon to read the database. It is fine to start a simple FastAPI app in backend/main.py just to serve products and images, then grow it into the agent backend in Problem 5.

**Follow-up prompt:** None needed.

---

## Problem 4 — Create Account and Log In

**Prompt 4:**
> Build a normal create-account/login flow. Create account: first name, last name, email, password (confirm password is a nice touch). Log in: email and password. New accounts go into the users table. Make sure to store passwords securely so hackers (human or AI) cannot access them. After you do that: the seed database will have a test user that we will use while building (email: test@campuscustoms.yale.edu, password: password). Confirm you can log in as that user, and that a brand new account you create also works. Update output/harness.md with how auth works (what you store for a user and how passwords are protected).

**Follow-up prompt:** None needed.

---

## Problem 5 — PydanticAI Agent Backend

**Prompt 5:**
> Build the shop chatbot as a PydanticAI agent behind FastAPI, plugged into your front-end chat widget. Put the API app in backend/main.py; that is the file you run with Uvicorn. Keep the agent as these four files next to it: backend/prompts/prompt.md (system prompt, grow this same file later), backend/agent.py (agent entry wiring), backend/tools.py (tools the agent can call), backend/models.py (Pydantic/PydanticAI structured types). In main.py, expose a chat route so a message from the website returns a reply from the agent (and whatever else you need for the products/auth). I will need the AI model API key for the agent.

**Follow-up prompt:**
> Put Campus Customs voice and safety basics into prompts/prompt.md (I will expand the tools and the safety later). Start or update types in models.py for chat replies/product cards as needed. In output/harness.md, note how the front end talks to FastAPI and how the agent is loaded (prompt file + model). Make sure the backend runs from the backend/ folder like this: uvicorn main:app --reload --port 8000

*What was lacking:* The first build ran the backend from the homework/4 folder on port 8001 (`uvicorn backend.main:app`), not from inside backend/ on port 8000. The harness also didn't yet explain how the frontend reaches FastAPI or how the agent loads its prompt and model.

---

## Problem 6 — Database Lookup Tools (Description, Price, Stock)

**Prompt 6:**
> We're going to now give the agent tools that look up real information from campus_customs.db: product description, price, and how many are in stock (by size and when the customer asks). The agent must use the database; it should not invent prices or quantities. If a size is out of stock, say so clearly.

**Follow-up prompt:**
> Expand prompts/prompt.md so the agent knows to call these tools for price and stock questions. Add or update return types in models.py. In output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

*What was lacking:* The tools were working, but the prompt didn't clearly map each kind of question (description, price, stock) to a tool, and the harness didn't explain why each field in the lookup results was chosen.

---

## Problem 7 — Chat Results as Product Cards on the Page

**Prompt 7:**
> We're going to add a neat feature to the site. When the customer asks about a type of item (for example "what hoodies do you have?") the agent should search the catalogue and the website should dynamically show those matching items as product cards (image, name, price, short info). This is an API contract: the agent returns structured product matches and the front end renders them on the website.

**Follow-up prompt:**
> After the dynamic product cards are loaded by this new feature, make sure the same single-item page behavior that we built in Problem 3 still works. Each product card, including the one the chat just put on the page, should still open that detail view (large image + full info) when clicked. Update the prompts/prompt.md and output/harness.md so it is clear how each search result reaches the page.

*What was lacking:* The first version didn't confirm that the cards the chat adds still open the single-item page. Because the matches panel sat at the top of every page, the detail view opened underneath it. The prompt and harness also didn't yet walk through how a search result travels from the agent to the page.

---

## Problem 8 — Customer Memory and Page Context

**Prompt 8:**
> Prompt 8 is customer memory. When a shopper is logged in, save their chat history in the database in an appropriate table and reload it when they return. The agent should know who is chatting (name, email); put that in agent deps (or an equivalent clean pattern) and/or tools the agent can call. Also pass enough page context that if someone is on a product page and asks "do you have this in pink", the agent knows which item they mean. Put the code for this in the agent context. Guests can still chat, but history only needs to persist for logged-in users. Document in output/harness.md: how user chat history is stored, what customer fields the agent sees, and how page context is passed.

**Follow-up prompt:** None needed.

---

## Problem 9 — Improvements (Front End)

**Prompt 9 (front-end improvements):**
> Front end:
> 1. I don't like that I have to scroll in order to see the products. Instead, create a carousel at the top so that I can see 3 products at a time, then from there show the full products, but 12 at a time, 3 rows of 4, and make the next pages so that you have to click through them like 1, 2, 3 and so on.
> 2. When featuring the products, change it so that the dark products, like a blue long sleeve or a black shirt, are NEVER against a black background, because then you can't see the product very well.

**Follow-up prompt:**
> Carousel should also go on the home page.

*What was lacking:* When asked where the carousel should go, I first chose the Products page only, but the Home page also needed it so products are visible without scrolling there too.

**Second follow-up prompt:**
> In the carousel there is too much white space below the product description, making it awkward and making a user have to scroll. Fix it.

*What was lacking:* The carousel cards were too tall: a large square image plus empty space under the text, because every card stretched to match the tallest one. The carousel didn't fit on screen, so the shopper still had to scroll.

**Prompt 9 (back-end improvements):**
> Hmm, are there any opportunities for parallelization?

> What about 1 and 3 for backend improvements? *(1 = stream the chat reply; 3 = process the product images in parallel)*

**Follow-up prompt:**
> Additionally, I need you to write an output/usability.md. For each improvement say: 1. what I added, 2. why it helps a Campus Customs shopper or the business. Also delineate/list the 2 front-end improvements and the back-end improvements so that it's easy for the graders to follow when they are looking at the write-up and testing the corresponding features.

*What was lacking:* The improvements were documented only in the technical harness. There was no grader-friendly write-up that separated front-end from back-end improvements and explained each one's value to shoppers and the business.

---

## Problem 10 — Storefront Design

**Prompt 10:**
> For prompt 10 we are going to get creative. We want it to feel like a real Campus Customs storefront: fonts, color hierarchy, motion, product presentation, chat feel. Once we are done designing we will create an output/design.md. It will include what changed and why it should help customers stick around and buy. Keep the explanation concrete and short.

**Follow-up prompts:**
> For design I'm thinking a posh feel, preppy, like yacht, sailboat, old money — like the J.Crew or Banana Republic website. Create a design in that theme.

> Can you feature models wearing the clothing at Yale? Maybe in the world and on campus. Can you source them from the world wide web? But also generate some or all too, in order to get the aesthetic we want.

> Better — I want models though. Can you make models outfitted in the clothing?

> Use the API key you already have access to.

> Do option 1. *(real Unsplash model photos in plain matching garments, with our real product prints added onto them)*

> Let it rip — the designs we talked about. We found a way to do it without the OpenAI API key; we were going to do some alternatives. *(more model looks made the same way, aimed at the planned campus, sailboat and harbor settings)*

> I kinda want movement, like the way they do on the J.Crew website. Do you know what I mean? Please articulate if you do.

> Yes, let's do that. All other elements should remain the same.

> Rotate the announcement bar; I'm fine with the lookbook change. *(keep the rotating bar; turn the lookbook into a sideways swipe row)*

> No, you didn't. I want the top section with the sailboat to have motion.

*What was lacking:* The hero's first version only crossfaded with a barely visible 8% zoom, so it read as still photos instead of J.Crew-style moving footage.

> OK, I see. It needs a little bit more motion than that, so maybe make the fade faster.

*What was lacking:* The second version moved, but slowly (5.5 s per scene, a 1.2 s fade), so it still felt calm rather than lively.

> I want a little slower.

*What was lacking:* The faster version (3.8 s per scene, a 0.7 s fade) went slightly too far, so I settled in between.

> Undo that last prompt (the usability.md rewrite). We're in Prompt 10, and for Prompt 10 I'm supposed to: 1. Add creative design so the site feels like a real Campus Customs storefront: fonts, color, hierarchy, motion, product presentation, chat and feel. Write output/design.md: what I changed and why it should help customers stick around and buy. Be concrete and short.

*What was lacking:* design.md had grown to about 1,700 words, which wasn't short. It's now organized by the brief's own headings with a few concrete bullets each.

*What was lacking:* The first design direction was a varsity campus-store look, not the posh, preppy heritage feel I wanted, and it had no lifestyle photography. The first lifestyle version had scenery but no people wearing the clothes. Generating models wasn't possible: the course Portkey key only serves a text model, and a free generator produced the wrong garment. So the final lookbook uses real Unsplash models in plain matching garments, with each product's real print added digitally.

---

## Problem 11 — Site Testing (App Check)

**Prompt 11:**
> Prompt 11 is called site testing (app check). I'm supposed to test the live site and document it in output/app_check.html, which is a page that I can double-click open. I'm also supposed to include clear screenshots and short captions for: 1. Chat checking the inventory level of an item (honest stock/price from the DB). 2. The dynamic search-result cards appearing after a category question (e.g. hoodies). 3. One of the usability features that I added in Problem 9.

**Follow-up prompt:**
> Once you do that, let me see the screenshots and short captions that you took.

> Last thing for Prompt 11: make the HTML easy to grade (a heading for each check, the screenshot, one or two sentences, and what the screenshot proves). Put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (for example app_check_images/inventory.png).

*What was lacking:* Nothing was missing from the request. On my side, the first inventory screenshot hid the product page's stock table behind the chat's product card panel, and the first pagination screenshot was mostly footer. Both were retaken before showing them. The first page also built the images into the HTML, and it wasn't laid out check by check for grading. It now links separate PNGs in `output/app_check_images/`, and each check has a heading, a screenshot, a short description and "What this proves".

---

## Problem 12 — Audit Trail, Safety, Finish Harness

**Prompt 12:**
> Called the audit trail, safety, finish harness. Keep an append-only output/audit_trail.json of agent-loop activity (time, tool name, short args/result, stop reason). Do not wipe it between runs. Once you do that, let's think of some safety rules.

**Follow-up prompts:**
> 1, 2, 3, 5, 7. I also want to come up with some guardrails so that the agent "behaves".

> As well as stopping rules: hunger + satiation.

> Yes, let's do all.

> Put all the safety rules that were created into prompts/prompt.md.

*What was lacking:* The audit trail and the first safety rules worked, but the agent had no explicit rules for when to keep looking (hunger) or when to stop (satiation). Testing showed it could fire 25 lookups for one broad question. The rules were also scattered across several prompt sections instead of one clear "Safety rules" section.

> Great, now that we are done with that, let's finish output/harness.md so that it is clear how the system works. Fill out the harness with the following and how they work: model fields in models.py and why you chose them; tools and abilities; safety rules; specs (loop limits, result caps, models, how to run front + back).

*What was lacking:* The harness had grown problem by problem, so its main sections were out of date (old run instructions on port 8001) and sections 8–10 (specs, limitations, file tree) were still placeholders. It's now reorganized into 8 clear main sections, with the per-problem build notes moved to an appendix (A1–A11).

---
