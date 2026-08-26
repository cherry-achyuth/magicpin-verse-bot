# AGENTS.md — Read this before touching any code

You are building a submission for the **magicpin AI Challenge ("Build Vera Better")**.
This file is binding. If anything you are about to do conflicts with this file,
stop and re-read `spec.md` and the files in `reference/` before proceeding.

## 0. Non-negotiable operating rules

1. **Ground truth lives in `reference/` and `dataset/`, not in your training data or
   general knowledge of "magicpin" or "Vera".** Before writing or changing any code
   that touches the contract (endpoints, payload shapes, scoring behavior), open and
   re-read the relevant section of:
   - `reference/challenge-brief.md` — the product spec, 4-context framework, rubric.
   - `reference/challenge-testing-brief.md` — the HTTP contract, phases, penalties.
   - `reference/examples/api-call-examples.md` — exact request/response JSON shapes.
   - `reference/examples/case-studies.md` — what a 9-10/10 message looks like, per category.
   - `reference/judge_simulator.py` — the actual scoring code you will be tested against locally.
   Do not guess a field name, endpoint path, or response shape. Copy it from these files.

2. **Never fabricate data in a composed message.** If a number, date, citation, or
   competitor name is not present in the `category`, `merchant`, `trigger`, or
   `customer` context objects passed into `compose()`, it must not appear in the
   output. This is graded and heavily penalized (case-studies.md, "no fabrication").

3. **Never hardcode a response to a specific test pair.** The bot must be a general
   composer that works on *any* (category, merchant, trigger, customer?) tuple,
   including ones it has never seen (post-submission context injection, Phase 3 in
   `challenge-testing-brief.md`). Special-casing `test_id` values, merchant names,
   or trigger ids anywhere in `bot.py` is a disqualifying shortcut — don't do it.

4. **Do not copy the wording of any case study into `bot.py`, prompt templates, or
   `submission.jsonl`.** `case-studies.md` explicitly states the judge runs a
   similarity check and penalizes near-duplicates. Use the case studies to learn the
   *shape* of good output (specificity, category voice, single CTA), never as text
   to lift.

5. **Match every schema exactly**, field names and casing included. The judge/harness
   is code, not a lenient human — a renamed field (`bodyText` instead of `body`) is a
   parse failure, not a style choice. Cross-check every JSON response your endpoints
   return against `reference/examples/api-call-examples.md` before considering a task
   done.

6. **Respect the two rules that are easy to miss and expensive to violate:**
   - `challenge-testing-brief.md` §7 example skeleton and the brief both allow URLs
     "when they add clear value" — **but** `api-call-examples.md` "Example F.4" scores
     a URL in the body as a **hard fail, -3 penalty, because Meta would reject it**.
     Resolve this conflict conservatively: **never put a raw URL in a message `body`.**
     If you need to reference a link, describe it in words. Document this decision in
     `submission/README.md`.
   - `/v1/tick` and `/v1/reply` have a **30-second hard budget**. If an LLM call risks
     exceeding it, return `{"actions": []}` (tick) or budget your prompt/model choice
     so you reliably finish — do not "fire and forget" background work; late
     responses are dropped and penalized as timeouts.

7. **Determinism.** `compose()` must be deterministic given the same inputs. Set
   `temperature=0` (or the closest equivalent) on every LLM call used for composition.

8. **Update `tasks.md` as you go.** Check off each task's checkbox only when its
   Acceptance Criteria are actually verified (tests pass, `judge_simulator.py`
   scenario runs, manual curl check, etc.) — not when code merely "looks done".
   If you discover a new subtask mid-implementation, add it under the right phase
   instead of silently doing extra work.

9. **Never invent challenge logistics.** `challenge-brief.md` §14 ("Logistics") is
   explicitly full of placeholders (`<e.g., 14 days from launch>`). Do not invent
   dates, prize amounts, or eligibility rules. Leave a note in
   `submission/README.md` that logistics are pending confirmation from magicpin,
   and ask Charan directly if the actual hackathon rules differ from this brief.

10. **Privacy/security**: the dataset is synthetic (see `challenge-brief.md` §15 and
    `challenge-testing-brief.md` §11). Do not add any code path that sends merchant
    or customer payload fields to a non-LLM third-party API. LLM API calls
    (Anthropic/OpenAI/etc.) are explicitly allowed and necessary.

## 0.1 Code style rules — comments and language

1. **Explain every file and every non-obvious function with a short comment**, written
   like you're explaining it to a smart friend who has never seen this project before.
   Use plain, everyday English. Short sentences. No jargon unless the word is
   genuinely the simplest way to say it (e.g. "endpoint" and "token" are fine;
   "idempotent," "orchestration," "leverage," "utilize" are not — say "safe to call
   twice," "the part that runs things in order," "use").
2. **Comments should read like a person wrote them, not like an AI generated them.**
   Concretely, that means:
   - No comment headers made of decorative lines (`# ====`, `# ------`) or
     "SECTION:" banners. Just write the sentence.
   - No comments that restate the obvious code (`# increment counter` above
     `count += 1`). Only comment on things that need explaining: *why* a choice was
     made, what a function is for, what a tricky bit of logic does.
   - No stiff, over-formal phrasing ("This function is responsible for the handling
     of..."). Write it the way you'd say it out loud: "This picks the right prompt
     for the trigger type."
   - Keep each comment short — one or two lines. If it needs a paragraph, the code
     probably needs breaking into smaller pieces instead.
3. **Every file should open with a 2-4 line comment** saying, in plain words, what
   this file does and why it exists — so someone opening `bot.py` cold understands
   its job in ten seconds.
4. This applies to `submission/README.md` too — write it in plain, simple English,
   like you're explaining the project to a teammate, not like a spec document.

## 0.2 Dependencies and versions — no version mismatches

1. **Always check the current stable version of every library before pinning it** —
   don't rely on memory for version numbers, they go stale. Look up FastAPI, uvicorn,
   pydantic, and whichever LLM SDK(s) you use, and pin to their current stable
   releases in `submission/pyproject.toml` / `requirements.txt`.
2. **Pin versions that are known to work together.** In particular: Pydantic v2 has a
   different API from v1 (FastAPI's request/response models must match whichever
   major version you pick — don't mix v1-style and v2-style code). Check that the
   FastAPI version you pick officially supports the Pydantic version you pick before
   writing any model code.
3. **Use the Python version actually installed in the dev/deploy environment** — check
   `python3 --version` before assuming a specific version's syntax is available
   (e.g. don't use a very new syntax feature if the deploy host runs an older Python).
4. **After installing dependencies, actually run the server once** (`uvicorn
   bot:app --port 8080`) before writing more code on top of it, to catch a version
   mismatch immediately rather than after building three more files on a broken
   foundation.
5. **Before deploying (Phase 8 in `tasks.md`), re-check that the exact same
   dependency versions are installed on the host as were used locally** — use a lock
   file (`requirements.txt` with pinned `==` versions, or `poetry.lock` /
   `uv.lock`) so "works on my machine" doesn't turn into "breaks on the server."

## 1. Source of truth hierarchy (if documents ever disagree)

1. `reference/judge_simulator.py` (it's what will actually score local runs)
2. `reference/challenge-testing-brief.md` + `reference/examples/api-call-examples.md` (the wire contract)
3. `reference/challenge-brief.md` (the product/composition spec)
4. `spec.md` and `tasks.md` in this repo (our own derived plan — must never contradict 1-3; if you find a contradiction, fix `spec.md`/`tasks.md`, don't silently follow the wrong one)
5. `reference/engagement-design.md` / `reference/engagement-research.md` — background only, describes magicpin's *internal, not-yet-built* production system. Useful for flavor and vocabulary, **not** a spec for this challenge. Do not implement anything from these two files that isn't also in the brief or testing brief.

## 2. Definition of done for the whole project

The project is done when all of the following are true simultaneously:

- [ ] `submission/bot.py` implements all 5 endpoints from `challenge-testing-brief.md` §2, verified against `judge_simulator.py` scenario `all` and `full_evaluation` running clean with no FAIL lines.
- [ ] `submission/submission.jsonl` has exactly 30 lines, one per `test_pairs.json` entry generated by `dataset/generate_dataset.py`, each a valid JSON object with keys `test_id, body, cta, send_as, suppression_key, rationale`.
- [ ] `submission/conversation_handlers.py` implements `respond(state, merchant_message) -> dict` and correctly passes the three replay scenarios in `challenge-testing-brief.md` §Phase 4 / `api-call-examples.md` Phase 4 (auto-reply hell, intent transition, hostile/off-topic).
- [ ] `submission/README.md` is ≤1 page, covers approach + tradeoffs + what additional context would have helped (per brief §7.3), and documents the URL policy decision from rule 6 above.
- [ ] Bot is deployed and reachable at a public HTTPS/HTTP URL; `/v1/healthz` returns 200 from the public internet.
- [ ] Every item in `tasks.md` is checked off with its acceptance criteria actually verified.
- [ ] Every file in `submission/` has a short, plain-English comment at the top and
      simple, human-sounding comments on the non-obvious parts (see §0.1) — no
      decorative banners, no stiff AI-sounding phrasing.
- [ ] All dependency versions are checked against current stable releases and pinned
      together in a lock file / pinned requirements file, and the server has actually
      been run locally to confirm no version mismatch (see §0.2).

Work through `tasks.md` in order. Do not skip ahead to deployment before the composer
and validation layer are passing local tests — a fast, wrong bot scores worse than a
slower, correct one within the 30s budget.
