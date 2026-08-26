# tasks.md — Build Plan

Work top to bottom. Each task has an **Acceptance Criteria** line — a task is only
checked off when that criteria is actually verified, not when the code merely exists.
Read `AGENTS.md` before starting Phase 0. Read the cited `reference/` section before
starting each task that names one.

---

## Phase 0 — Project setup

- [x] **0.1 Read all context.** Open and read fully, in this order: `AGENTS.md`,
  `spec.md`, `reference/challenge-brief.md`, `reference/challenge-testing-brief.md`,
  `reference/examples/api-call-examples.md`, `reference/examples/case-studies.md`,
  `reference/judge_simulator.py`, `dataset/generate_dataset.py`.
  **Acceptance:** you can state, from memory, all 5 endpoint names, the 3 `/v1/reply`
  action types, and the 5 rubric dimensions without re-opening the files.

- [x] **0.2 Python project scaffold.** Create `submission/pyproject.toml` (or
  `requirements.txt`), a virtualenv, and install: `fastapi`, `uvicorn`, `pydantic`,
  plus an LLM SDK for at least one provider (`anthropic` and/or `openai`).
  **Acceptance:** `uvicorn submission.bot:app --port 8080` starts without import
  errors (a stub `bot.py` with just `/v1/healthz` is fine at this point).

- [x] **0.3 Generate the full dataset.** Run `python dataset/generate_dataset.py
  --seed-dir dataset --out dataset/expanded`. This expands the 10 merchant / ~15-25
  customer/trigger seeds into the full 50 merchants / 200 customers / 100 triggers /
  `test_pairs.json` (30 canonical pairs) that the judge actually uses.
  **Acceptance:** `dataset/expanded/` contains `categories/` (5 files),
  `merchants/` (50 files), `customers/` (200 files), `triggers/` (100 files), and
  `test_pairs.json` (30 entries). Confirm counts with a one-line Python check.

- [x] **0.4 Secrets.** Create `submission/.env.example` documenting required env vars
  (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`) and add a real `.env` (gitignored) for
  local dev. **Acceptance:** `.env` is in `.gitignore`; `.env.example` has no real key.

---

## Phase 1 — Data models

- [x] **1.1 Pydantic models for the 4 contexts.** In `submission/models.py`, define
  `CategoryContext`, `MerchantContext`, `TriggerContext`, `CustomerContext` matching
  field names exactly from `challenge-testing-brief.md` §3. Use `Optional`/defaults
  generously — real payloads may omit fields your composer doesn't strictly need.
  **Acceptance:** loading every file in `dataset/expanded/categories/`,
  `dataset/expanded/merchants/`, `dataset/expanded/customers/`,
  `dataset/expanded/triggers/` into the matching model succeeds with zero validation
  errors (write a throwaway `scripts/validate_dataset.py` to prove this, then delete
  or keep it under `submission/scripts/`).

- [x] **1.2 Request/response models for the wire contract.** Define Pydantic models
  for every request/response body in `challenge-testing-brief.md` §2:
  `ContextPushRequest`, `ContextPushResponse` (200/409/400 variants), `TickRequest`,
  `TickResponse`/`Action`, `ReplyRequest`, `ReplyResponse` (send/wait/end variants),
  `HealthzResponse`, `MetadataResponse`.
  **Acceptance:** every example JSON in `reference/examples/api-call-examples.md`
  parses into (or serializes from) these models without a schema mismatch — write a
  quick test that round-trips a few of the literal example payloads.

- [x] **1.3 In-memory store.** Implement a `ContextStore` class: keyed by
  `(scope, context_id)` → `{version, payload}`, with an idempotent `put` (rejects
  stale/equal versions per §2.1 of the testing brief) and lookups by id and by scope.
  Also a `ConversationStore` keyed by `conversation_id` → ordered turn history +
  status (`open`/`ended`/`waiting_until`).
  **Acceptance:** unit tests: pushing v1 then v1 again returns the 409 shape; pushing
  v2 after v1 replaces and a v1-again push after that also 409s with
  `current_version: 2`.

---

## Phase 2 — Composer core

- [x] **2.1 LLM client abstraction.** `submission/llm_client.py` — a thin wrapper
  exposing `complete(system, user, temperature=0) -> str` with at least one real
  provider implemented (mirror the provider-selection pattern in
  `reference/judge_simulator.py`'s `LLMProvider` subclasses for structure, but write
  your own — don't import from the judge file). Enforce `temperature=0` for
  determinism (spec.md §6.4, brief §7.1).
  **Acceptance:** a manual smoke test call returns text; swapping the env var model
  name doesn't require a code change.

- [x] **2.2 Prompt template — merchant-facing composer.** Build the system/user
  prompt that takes `CategoryContext + MerchantContext + TriggerContext` and asks the
  LLM to return structured JSON: `body, cta, send_as="vera", rationale`. Bake in,
  as instructions (not hardcoded text): use the category's `voice`, cite `digest`
  sources when used, prefer `offer_catalog` service+price patterns over generic
  discounts, single CTA, last-sentence CTA, match `identity.languages` /
  code-mix, use owner's first name when present, lean on social-proof and
  ask-the-merchant levers (brief §10, under-used by production Vera).
  **Acceptance:** composing for the Dr. Meera / research-digest example from
  `challenge-brief.md` Appendix A produces a message that a human review confirms
  hits: specific number(s), source citation, clinical/peer voice, single open-ended
  CTA in the last sentence, no fabricated facts. (Don't aim to reproduce the example
  text — produce your own equivalent-quality output.)

- [x] **2.3 Trigger-kind dispatch.** Route to prompt variants (or prompt-parameter
  variants) by `trigger.kind` — at minimum distinguish: research/compliance digest
  framing, performance spike/dip framing, milestone framing, dormancy/re-engagement
  framing, recall/lapse framing (customer-facing), appointment-reminder framing,
  review-theme framing, seasonal/trend framing, external event (festival/weather/news)
  framing. Cross-check the full kind list against `challenge-brief.md` §4.3
  (external + internal trigger kinds) — don't miss any.
  **Acceptance:** every trigger `kind` present in `dataset/expanded/triggers/` maps
  to a defined dispatch branch (log/assert on an unhandled kind rather than silently
  falling through to a generic prompt with no framing).

- [x] **2.4 Customer-facing composer path.** When `customer` is populated, `send_as`
  must be `"merchant_on_behalf"`. Prompt must additionally honor
  `CustomerContext.identity.language_pref`, `relationship` (visit history / lapse
  state), `preferences.preferred_slots`, and never claim consent scope beyond
  `consent.scope`. Category voice rules for *customer-facing* copy (e.g., dentists:
  no "cure"/"guaranteed") apply here even more strictly than merchant-facing.
  **Acceptance:** composing Appendix B's Priya/recall_due scenario produces
  `send_as: merchant_on_behalf`, references the real active offer + real slots from
  the merchant's `offers`, honors hi-en code-mix, and uses a multi-choice slot CTA
  (the one documented exception to "single binary CTA" — booking flows, per
  `api-call-examples.md` Example 2.9).

- [x] **2.5 Post-LLM validation/repair layer.** `submission/validators.py`,
  deterministic Python, run on every composed message before it's returned or sent:
  - reject/strip raw URLs from `body` (AGENTS.md rule 6)
  - enforce single-CTA shape (reject if `body` contains multiple explicit asks)
  - enforce CTA lands in/near the last sentence
  - anti-repetition: compare against this `conversation_id`'s prior sent bodies
    (exact-match and near-duplicate via a cheap similarity check); reject/regenerate
    on match
  - basic fabrication guard: flag numbers/proper nouns in `body` that don't appear
    anywhere in the input contexts (heuristic string/number matching is fine — this
    doesn't need to be perfect, it needs to catch obvious hallucination)
  - language-preference check: if `hi` is expected and the body is pure English (or
    vice versa), flag for regeneration
  On any failed check, re-prompt once with the failure reason appended to the prompt;
  if it fails twice, fall back to a safe minimal templated message rather than
  sending something that violates the rules.
  **Acceptance:** unit tests feeding the validator known-bad examples (a body with 2
  CTAs, a body with a URL, a body repeating a prior message, a body with a "38%"
  number not present in any input context) — each is caught.

---

## Phase 3 — HTTP API (`submission/bot.py`)

- [x] **3.1 `GET /v1/healthz`.** Returns `status`, `uptime_seconds`,
  `contexts_loaded` counts per scope from the `ContextStore`.
  **Acceptance:** matches `api-call-examples.md` Example 1.1 / 1.7 shapes exactly at
  both zero-state and post-warmup state.

- [x] **3.2 `GET /v1/metadata`.** Returns static team/bot identity (Charan can fill
  in real team name/members/contact — do not invent these, ask if unclear).
  **Acceptance:** matches Example 1.2 shape.

- [x] **3.3 `POST /v1/context`.** Wire to `ContextStore.put`; return 200/409/400 per
  spec. Validate `scope` is one of `category|merchant|customer|trigger`; 400 with
  `reason: "invalid_scope"` otherwise.
  **Acceptance:** replays Examples 1.3–1.6 and 2.1, 2.8 from `api-call-examples.md`
  and gets byte-for-byte-equivalent (ignoring timestamps) response shapes.

- [x] **3.4 `POST /v1/tick`.** For each id in `available_triggers`: look up the
  trigger, resolve its `merchant_id` (and `customer_id` if customer-scoped), resolve
  the merchant's `category_slug` → category context; if any required context is
  missing, skip that trigger (don't error the whole tick). Run the composer
  (Phase 2) respecting the suppression_key dedup (don't re-fire a trigger whose
  `suppression_key` was already sent and not yet expired) and the "one action per
  (merchant_id, conversation_id) per tick" rule. Return within budget — if the
  composer can't finish in time, return `{"actions": []}` rather than blocking.
  **Acceptance:** replays Examples 2.2, 2.3, 2.9 — including the "no trigger worth
  acting on" empty-actions case and the customer-scoped trigger case.

- [x] **3.5 `POST /v1/reply`.** Look up conversation state; run the reply-composer
  (Phase 4) to decide `send`/`wait`/`end`; append the turn to conversation history;
  return within 30s.
  **Acceptance:** replays Examples 2.4 (engaged), 2.5 (auto-reply), 2.6 (hard no),
  2.7 (curveball off-topic) and produces responses that satisfy the same rules the
  "Good bot response" examples demonstrate (not necessarily identical text).

- [x] **3.6 Error handling & malformed-input resilience.** Never let an unhandled
  exception produce a non-JSON 500 — catch, log, and return a well-formed error body
  where the contract defines one (`/v1/context` 400) or a safe empty/negative result
  otherwise (e.g., `/v1/tick` → `{"actions": []}` rather than crashing the process).
  **Acceptance:** feeding each endpoint a deliberately malformed body (missing
  required field, wrong type) doesn't crash the server and doesn't return `-2`-style
  malformed-response shapes back to the judge.

---

## Phase 4 — Multi-turn conversation intelligence (`submission/conversation_handlers.py`)

- [x] **4.1 Conversation state machine.** Define `ConversationState` (turns so far,
  merchant/customer id, trigger that started it, count of consecutive identical
  merchant messages, count of consecutive unanswered nudges, detected language).
  **Acceptance:** state correctly accumulates across a simulated 5-turn exchange in a
  unit test.

- [x] **4.2 Auto-reply detector.** Flag when the incoming `message` matches (exact or
  near-exact) a prior message from the same `from_role` in the same conversation —
  the brief's stated heuristic is "same message verbatim 3+ times." Implement the
  graduated response: 1st occurrence → treat as possibly real, respond normally;
  2nd occurrence of the *same* text → `wait` (multi-hour backoff); 3rd+ → `end`.
  **Acceptance:** replays `api-call-examples.md` Example 4.1 turns 1-4 and produces
  `send` → `wait` → `end` in that order.

- [x] **4.3 Intent-transition detector.** Detect merchant messages that are clear
  affirmative commitments ("let's do it", "ok go ahead", "yes send it", "I want to
  join" — build a small classifier: an LLM call with temperature=0 and a tight
  prompt is fine, or a keyword/pattern heuristic if you want it fast and free — your
  choice, document which in `submission/README.md`). On detection, the next response
  must move to concrete action (what happens next, a scoped commitment) and must
  **not** ask another qualifying question.
  **Acceptance:** replays Example 4.2 turn 3 and the response is judged (by a
  second-pass LLM self-check, or by a human) to *not* contain a question whose
  purpose is further qualification.

- [x] **4.4 Hostile/off-topic handler.** Detect clearly hostile/opt-out language →
  `end` (optionally with one short apology `send` first). Detect off-topic-but-not-
  hostile asks → politely decline the out-of-scope part and redirect to the live
  thread without re-introducing yourself or losing context.
  **Acceptance:** replays Example 4.3 (hostile) and Example 2.7 (curveball,
  off-topic-not-hostile) and produces responses matching the documented "Good bot
  response" pattern for each.

- [x] **4.5 Wire `conversation_handlers.respond()` into `/v1/reply`.** Confirm Phase
  3.5 actually calls into this module rather than duplicating logic inline.
  **Acceptance:** code review — one code path, not two divergent implementations.

---

## Phase 5 — Test-pair submission generation

- [x] **5.1 Submission generator script.** `submission/scripts/generate_submission.py`
  — loads `dataset/expanded/test_pairs.json` (30 pairs), for each pair resolves the
  full category/merchant/trigger/customer(if any) contexts from
  `dataset/expanded/`, calls the *same* composer used by `/v1/tick` (no
  bot-vs-submission logic divergence), and writes `submission/submission.jsonl`.
  **Acceptance:** `submission/submission.jsonl` has exactly 30 lines; each line
  parses as JSON with exactly the keys `test_id, body, cta, send_as,
  suppression_key, rationale`; `test_id` values match `test_pairs.json` 1:1.

- [x] **5.2 Quality pass on the 30 outputs.** Run every generated message through the
  Phase 2.5 validators (should already pass since the same composer path is used —
  this is a regression check) and spot-check at least 2 outputs per category (10
  total) against the `case-studies.md` "Cross-case patterns" checklist.
  **Acceptance:** zero validator failures across all 30; the 10 spot-checked outputs
  each satisfy all 10 cross-case patterns (source citation, real numbers, owner name,
  single low-friction next step, customer-fit where applicable, correct vocabulary,
  a judgment call where relevant, meaningful conversation_id, accurate rationale, no
  repetition/fabrication).

---

## Phase 6 — Local judge testing

- [x] **6.1 Configure `judge_simulator.py`.** Set `BOT_URL`, `LLM_PROVIDER`,
  `LLM_API_KEY` at the top of `reference/judge_simulator.py` (or override via env if
  you prefer — check the file for how it reads config).
  **Acceptance:** `python reference/judge_simulator.py` with `TEST_SCENARIO =
  "warmup"` passes against your running `bot.py`.

- [x] **6.2 Run `all`.** `python reference/judge_simulator.py` with scenario `all`
  against a locally running `bot.py` (`uvicorn submission.bot:app --port 8080`).
  **Acceptance:** no `[FAIL]` lines; review every `[WARN]`; average dimension scores
  ≥7/10 (per the simulator's own "7+ is good" bar).

- [x] **6.3 Run `full_evaluation`.** Same as above with the most thorough scenario.
  **Acceptance:** same bar as 6.2; capture the output as
  `submission/local_eval_report.txt` for your own record (not required by the
  challenge, but useful evidence of iteration for the hackathon presentation).

- [x] **6.4 Fix and re-run.** For any dimension consistently scoring below 7, go back
  to Phase 2 (composer/prompt) or Phase 2.5 (validators) — not Phase 3 (transport) —
  since low scores are almost always a composition-quality problem, not a wiring
  problem. Re-run 6.2 after each fix.
  **Acceptance:** two consecutive clean `all` runs with no regressions.

---

## Phase 7 — README and packaging

- [x] **7.1 Write `submission/README.md`** (≤1 page): approach (composer
  architecture, model(s) used, dispatch-by-kind strategy), tradeoffs made (e.g.,
  heuristic vs. LLM intent-detection, URL policy decision from AGENTS.md rule 6),
  and what additional context would have helped most (per brief §7.3 — be specific
  and honest, e.g. "a real per-merchant reply-rate history would sharpen cadence
  planning").
  **Acceptance:** fits on one printed page; a fresh reader with no other context
  understands the approach in under 2 minutes.

- [x] **7.2 Fill in `GET /v1/metadata`** with real values (team name, member(s),
  actual model string in use, contact email, version, submission timestamp) — ask
  Charan for team name/members/contact if not already provided.
  **Acceptance:** no placeholder text ("Team Alpha", "Alice") remains.

- [x] **7.3 Final file check.** Confirm `submission/` contains exactly: `bot.py`,
  `submission.jsonl`, `README.md`, `conversation_handlers.py`, plus whatever support
  modules `bot.py` imports (`models.py`, `llm_client.py`, `validators.py`,
  `context_store.py`, etc. — supporting modules are fine, brief only mandates the
  four named files exist).
  **Acceptance:** `python -c "import bot"` (or the equivalent) works from a clean
  virtualenv with only the declared dependencies installed.

---

## Phase 8 — Deployment

- [ ] **8.1 Choose a host** (Render/Fly/Railway/cloud VM/ngrok — spec.md §9) and
  deploy `bot.py`. Set the LLM API key as a platform secret, not in code.
  **Acceptance:** `curl https://<host>/v1/healthz` returns 200 from a machine outside
  your dev environment (e.g., ask a friend, or curl from your phone's hotspot).

- [ ] **8.2 Load/latency sanity check.** Simulate a handful of concurrent
  `/v1/tick` and `/v1/reply` calls (a simple script hitting the deployed URL) and
  confirm p95 latency stays comfortably under the 30s budget, and under the "10
  requests/sec from judge" ceiling in `challenge-testing-brief.md` §5 your host
  doesn't rate-limit or cold-start badly.
  **Acceptance:** no request exceeds ~15s in the sanity check (leaving headroom under
  the 30s hard limit); no cold-start-induced timeout on the first request after idle.

- [ ] **8.3 Re-run `judge_simulator.py` against the deployed URL** (not localhost).
  **Acceptance:** same pass bar as Phase 6, now against the real deployment.

- [ ] **8.4 Submit.** Provide the public URL via whatever the actual hackathon's
  submission portal is (not specified in the brief — confirm with the organizers/
  Charan; do not guess a portal or process, per AGENTS.md rule 9).

---

## Phase 9 — Hackathon presentation polish (optional but recommended)

- [ ] **9.1 One-page architecture diagram** (composer → validators → HTTP layer →
  conversation state machine) for the live pitch.
- [ ] **9.2 A 2-3 minute demo script**: show a `/v1/tick` producing a message, a
  `/v1/reply` auto-reply-detection sequence, and an intent-transition sequence live
  — these are the most visually convincing differentiators per the brief's stated
  pain points (§3 "today's biggest pain points").
- [ ] **9.3 Have `local_eval_report.txt` (Phase 6.3) and a short "why we score well
  on each of the 5 dimensions" note ready** for Q&A.

**Acceptance for Phase 9:** judged by Charan's own comfort presenting it — no
automated check.
