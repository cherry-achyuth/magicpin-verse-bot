# spec.md — Vera-Better Bot: Technical Specification

> Derived from `reference/challenge-brief.md` and `reference/challenge-testing-brief.md`.
> This file is a build-oriented restatement, not a replacement — when in doubt, the
> `reference/` files win (see `AGENTS.md` §1 source-of-truth hierarchy).

## 1. What we're building

An HTTP service (`submission/bot.py`) that plays the role of **Vera**, magicpin's
merchant-facing + customer-facing WhatsApp AI assistant, and does it *better* than
production Vera along 5 judged dimensions: specificity, category fit, merchant fit,
trigger relevance, engagement compulsion.

The core capability is a **composer**:

```
compose(category, merchant, trigger, customer=None) -> {
    body, cta, send_as, suppression_key, rationale
}
```

...wrapped in a stateful HTTP service that the judge harness calls over the challenge
lifetime (warmup → 60-min test window → adaptive context injection → replay for top 10).

## 2. The 4-context data model

Read `reference/challenge-brief.md` §4 for full field-by-field detail and
`reference/challenge-testing-brief.md` §3 for the exact wire JSON shapes. Summary:

| Context | Purpose | Populated when |
|---|---|---|
| `CategoryContext` | vertical knowledge: voice, offer catalog, peer stats, digest, seasonal beats, trend signals | always |
| `MerchantContext` | this business's live state: identity, subscription, performance, offers, conversation history, customer aggregate, derived signals | always |
| `TriggerContext` | the event that justifies messaging *now* | always — every message needs one |
| `CustomerContext` | the merchant's own customer, when messaging on their behalf | only for customer-facing (`send_as=merchant_on_behalf`) sends |

Implement these as typed Python models (dataclasses or Pydantic models — Pydantic is
preferable since FastAPI request bodies are `dict[str, Any]` per the contract, and
Pydantic gives you validation for free internally). Field names must mirror
`challenge-testing-brief.md` §3 exactly, since that's the shape the judge posts.

## 3. Composition rules the output must satisfy

From `challenge-brief.md` §5 "Constraints your bot must respect":

1. First outbound to a merchant/customer in a fresh 24h session = template-shaped
   (`template_name` + `template_params`). Free-form after a reply within 24h.
2. No hard body length cap — concise, context-appropriate.
3. **Single primary CTA.** Binary (YES/STOP) for action triggers; none for pure-info.
   Never multiple asks in one message (anti-pattern, §11 of brief).
4. **No raw URLs in `body`** (see `AGENTS.md` rule 6 — this overrides the brief's
   more permissive language given the explicit -3 penalty example in
   `api-call-examples.md` Example F.4).
5. Specificity wins — anchor on a verifiable fact from the contexts. Never
   "X% off" when a service+price pattern from `offer_catalog` is available.
6. Voice match — peer/colleague tone per `CategoryContext.voice`, not promotional.
7. Hindi-English code-mix when the merchant's/customer's language preference calls
   for it (`identity.languages` contains `"hi"`, or `language_pref` says `hi-en mix`).
8. **Never fabricate.** No data outside the 4 contexts.

Additional anti-patterns to actively check for post-composition (brief §11):
- generic discount framing over available service+price
- multiple CTAs
- buried CTA (must land in the last sentence)
- promotional tone in clinical/peer categories (dentists, doctors, lawyers)
- hallucinated data
- long preambles / re-introducing yourself mid-conversation
- ignoring language preference
- verbatim repeat of a prior message in the same conversation

Compulsion levers to deliberately use, per `challenge-brief.md` §10 (production
Vera under-uses **social proof** and **asking the merchant** — lean into these two
for differentiation):
specificity/verifiability, loss aversion, social proof, effort externalization,
curiosity, reciprocity, asking the merchant a question, single binary commitment.

## 4. HTTP contract (the wire-level truth)

Full detail: `reference/challenge-testing-brief.md` §2, worked examples in
`reference/examples/api-call-examples.md`. Five endpoints, all HTTPS/HTTP, JSON,
UTF-8:

| Endpoint | Method | Purpose | Budget |
|---|---|---|---|
| `/v1/context` | POST | receive category/merchant/customer/trigger context push, idempotent on `(context_id, version)` | 5s |
| `/v1/tick` | POST | periodic wake-up; bot may proactively return `actions[]` | 30s (design for well under) |
| `/v1/reply` | POST | synchronous reply to a merchant/customer message; bot returns `send`/`wait`/`end` | 30s |
| `/v1/healthz` | GET | liveness + `contexts_loaded` counts | 2s, polled every 60s, 3 fails = disqualified for the slot |
| `/v1/metadata` | GET | team/bot identity | 2s |

Key behaviors to implement precisely:
- `/v1/context`: higher `version` for same `context_id` replaces atomically; equal-or-lower
  version → `409 {"accepted": false, "reason": "stale_version", "current_version": N}`.
- `/v1/tick`: at most one action per `(merchant_id, conversation_id)` per tick; up to
  20 actions per tick; empty `actions: []` is valid and often correct (restraint is
  rewarded, spam is penalized).
- `/v1/reply`: must respond within 30s with exactly one of `send` / `wait` / `end`.
- State persists in memory for the life of the test process — no restarts assumed
  mid-test. An optional `POST /v1/teardown` may arrive at test end; wipe state on it.

## 5. Conversation intelligence (multi-turn, `conversation_handlers.py`)

Optional per the brief but **required for a strong submission** since it's explicitly
the tiebreaker and the Phase 4 replay test (worth up to +30 points) only runs against
it. Implement `respond(state, merchant_message) -> dict`. Must correctly handle the
three canonical scenarios in `challenge-testing-brief.md` §Phase 4 and
`api-call-examples.md` Phase 4:

1. **Auto-reply detection** — same canned message verbatim ≥3× → detect on the 2nd
   occurrence (soft backoff via `wait`), and `end` gracefully by the 3rd/4th. Hint
   from the brief: "same message verbatim 3+ times = auto-reply."
2. **Intent transition** — merchant says an equivalent of "yes let's do it" after
   qualification turns → immediately switch to action mode (concrete next step,
   binary confirm CTA), never ask another qualifying question. This is the single
   most explicitly penalized failure mode in the brief (§9 Pattern D, and
   `api-call-examples.md` Example 4.2 "Bad bot response").
3. **Hostile/off-topic** — abusive or clearly-done merchant → `end` (or one short
   apology + `none` CTA, then end). Off-topic-but-not-hostile → politely decline what's
   out of scope and redirect back to the live thread without restarting/re-introducing.

Also design for (open challenges, §12 of the brief — extra credit, not required, but
cheap to get mostly right if the state machine is clean):
- language detection per turn (merchant may code-switch mid-conversation)
- knowing when to stop after 3 unanswered nudges
- multi-turn cadence planning within the 24h session window

## 6. Composer architecture (recommended, not mandated — brief §13 is explicit that
approach is free)

1. **Prompt template** takes the (up to 4) contexts as structured input, dispatches
   by `trigger.kind` to a kind-specific prompt variant (research-digest framing vs.
   recall-reminder framing vs. perf-dip framing, etc. — see `engagement-design.md`
   "Composer dispatches by kind" for the *idea*, but write your own prompts; don't
   port magicpin's internal, unbuilt code).
2. **Post-LLM validation layer** (deterministic Python, not another LLM call) that
   rejects/repairs output violating: single-CTA rule, no-URL rule, language-match,
   anti-repetition against `conversation_history`, and a basic fabrication check
   (every number/date/citation in the body should be traceable to a value present in
   the input contexts — this can be a heuristic, not a proof).
3. **Retrieval** over `CategoryContext.digest` / `patient_content_library` items when
   there are many (pick the most relevant to the trigger and merchant signals) rather
   than dumping the whole list into the prompt.
4. **LLM provider abstraction** — support at least one frontier model; the challenge
   is explicitly LLM-agnostic. `reference/judge_simulator.py` already supports
   openai/anthropic/gemini/deepseek/groq/ollama/openrouter as a reference for what
   "pluggable provider" looks like — mirror that flexibility in `bot.py`'s own LLM
   client so Charan can swap providers by env var, not by editing prompt code.

## 7. Deliverables (`challenge-brief.md` §7)

All final artifacts live in `submission/`:

- `bot.py` — the FastAPI (or equivalent) service implementing all 5 endpoints and
  the composer. Must run standalone: `uvicorn bot:app --host 0.0.0.0 --port 8080`.
- `submission.jsonl` — 30 lines, one JSON object per line, one per canonical test
  pair from `dataset/test_pairs.json` (generate this file first — see tasks.md
  Phase 1). Keys: `test_id, body, cta, send_as, suppression_key, rationale`.
- `README.md` — ≤1 page: approach, tradeoffs, what additional context would have
  helped most. Also document the URL policy decision (AGENTS.md rule 6).
- `conversation_handlers.py` — optional per spec but treat as required per §5 above.

## 8. Local self-test loop

Use `reference/judge_simulator.py` throughout development, not just at the end:

```bash
export BOT_URL=http://localhost:8080
# provider/key config is at the top of judge_simulator.py — set LLM_PROVIDER + LLM_API_KEY
python reference/judge_simulator.py
```

It supports scenarios: `warmup`, `phase2_short`, `auto_reply_hell`,
`intent_transition`, `hostile`, `all`, `full_evaluation`. Run `all` after every
significant change; run `full_evaluation` before considering the bot submission-ready.

## 9. Deployment

Any host that gives a public URL is acceptable (`challenge-testing-brief.md` §6):
Render, Fly.io, Railway, a cloud VM, or an ngrok tunnel to localhost for a live
hackathon demo. Requirements:
- reachable at `https://<host>/v1/*` (or `http://` for local/demo use)
- `/v1/healthz` returns 200 before you submit the URL
- environment holds your LLM API key as a secret, never committed to the repo

## 10. Explicitly out of scope for this challenge

Do not build any of the following even though they appear in `engagement-design.md`
/ `engagement-research.md` (those describe magicpin's *own, not-yet-built* internal
system — background reading only, per `AGENTS.md` §1):
- real WhatsApp Business API / Kaleyra template registration or delivery
- real Google Business Profile read/write integration
- a persistent database beyond what's needed to hold state for a single test run
- customer data source-of-truth integrations (Practo, CSV upload, etc.)
- authentication/authorization on the 5 endpoints unless you want it for your own
  protection — the judge harness doesn't send credentials per the testing brief
