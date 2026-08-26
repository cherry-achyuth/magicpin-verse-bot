# magicpin AI Challenge — "Build Vera Better" — Project Package

This folder is a ready-to-open workspace for building your challenge submission with
**Google Antigravity**. Everything Antigravity needs to work correctly, without
guessing or hallucinating requirements, is already here.

## What's in this folder

```
.
├── AGENTS.md                    ← read by the agent FIRST, every session. Strict rules.
├── spec.md                      ← the technical spec Antigravity builds against
├── tasks.md                     ← the full task breakdown with checkboxes + acceptance criteria
├── reference/                   ← the ORIGINAL challenge documents, verbatim (ground truth)
│   ├── challenge-brief.md
│   ├── challenge-testing-brief.md
│   ├── engagement-design.md         (background only — see AGENTS.md §1)
│   ├── engagement-research.md       (background only — see AGENTS.md §1)
│   ├── judge_simulator.py           (local scoring tool — use this constantly)
│   └── examples/
│       ├── api-call-examples.md     (exact request/response JSON — copy, don't guess)
│       └── case-studies.md          (10 worked "what good looks like" examples)
├── dataset/                     ← the official base dataset (seeds + generator)
│   ├── categories/*.json            (5 fully-populated CategoryContexts)
│   ├── merchants_seed.json
│   ├── customers_seed.json
│   ├── triggers_seed.json
│   └── generate_dataset.py          (expands seeds → 50 merchants / 200 customers /
│                                      100 triggers / 30 canonical test pairs)
└── submission/                  ← EMPTY. Antigravity builds your deliverables here:
                                     bot.py, submission.jsonl, README.md,
                                     conversation_handlers.py
```

## How to use this with Antigravity

1. Open this entire folder as your Antigravity workspace.
2. Start a new agent task with a prompt like:

   > Read AGENTS.md, spec.md, and tasks.md. Then work through tasks.md phase by
   > phase, checking off each task's checkbox only once its acceptance criteria is
   > actually verified. Ask me before Phase 8 (deployment) if you need hosting
   > credentials or a team name for /v1/metadata.

3. Let it work through Phase 0 → Phase 8 in `tasks.md` in order. The phases are
   deliberately sequenced so the agent builds the composer and validates it locally
   (with `reference/judge_simulator.py`) *before* wiring up HTTP, and wires up HTTP
   *before* deploying — this avoids the common failure mode of a nicely-deployed bot
   that composes mediocre messages, which is the actual thing being scored.
4. `AGENTS.md` contains a "definition of done" checklist — the project isn't
   finished until every line in it is true.
5. When Antigravity has a substantive question (team name for `/v1/metadata`, which
   LLM provider/API key to use, where to deploy), it's instructed to ask you rather
   than invent an answer — expect a few checkpoints like that.

## Two things worth knowing before you start

- **The brief and the examples file disagree about URLs in messages.**
  `challenge-brief.md` says URLs are "allowed when they add clear value," but
  `reference/examples/api-call-examples.md` (Example F.4) explicitly scores a URL in
  the message body as a **hard fail with a -3 penalty**, because Meta would reject
  it. `AGENTS.md` resolves this conservatively: **never put a raw URL in a message
  body.** This is documented in the agent's rules so it won't quietly get this wrong.

- **The actual hackathon logistics (dates, team size, submission portal, prizes)
  are not in the brief** — `challenge-brief.md` §14 is explicitly full of
  placeholders. Nobody should invent these. If you know the real logistics from
  magicpin, tell Antigravity directly when it asks (Phase 8.4 in `tasks.md`); don't
  let it guess.

## Recommended local dev loop

```bash
# Start server from project root:
uvicorn submission.bot:app --host 0.0.0.0 --port 8080 --reload

# Generate dataset (if not already expanded):
python dataset/generate_dataset.py --seed-dir dataset --out dataset/expanded

# Run local judge evaluation:
export BOT_URL=http://localhost:8080
python reference/judge_simulator.py
```

Iterate on `submission/bot.py` (and its supporting modules) until
`judge_simulator.py`'s `all` and `full_evaluation` scenarios pass clean, then move to
deployment (`tasks.md` Phase 8).

Good luck — build something that would actually beat production Vera on the things
that matter: specificity, category-correct voice, real merchant/customer
personalization, and knowing when to stop talking.
