# Vera Merchant AI Assistant — Submission README

This project builds Vera, an autonomous merchant engagement assistant for magicpin. Vera composes highly specific, data-backed messages that prompt merchants and their customers to take action.

## 🚀 Live Deployment & Links

- **Live Service URL**: [`https://magicpin-verse-bot.onrender.com`](https://magicpin-verse-bot.onrender.com)
- **Health Check**: [`https://magicpin-verse-bot.onrender.com/v1/healthz`](https://magicpin-verse-bot.onrender.com/v1/healthz)
- **Metadata**: [`https://magicpin-verse-bot.onrender.com/v1/metadata`](https://magicpin-verse-bot.onrender.com/v1/metadata)
- **Interactive API Docs (Swagger)**: [`https://magicpin-verse-bot.onrender.com/docs`](https://magicpin-verse-bot.onrender.com/docs)
- **GitHub Repository**: [`https://github.com/cherry-achyuth/magicpin-verse-bot`](https://github.com/cherry-achyuth/magicpin-verse-bot)

## 1. Approach and Architecture

Vera combines four context layers into every generated message:
1. **Category Context**: Sets the exact professional voice (clinical peer-to-peer for dentists, operator-to-operator for restaurants, motivational for gyms, warm for salons, trustworthy for pharmacies).
2. **Merchant Context**: Grounds identity, owner name, location, and active catalog offers.
3. **Trigger Context**: Provides the "why now" (research digests, competitor alerts, demand spikes, performance dips, festivals).
4. **Customer Context**: Personalizes customer recall and refill reminders with preferred appointment slots and past service dates.

### Composition & Validation Pipeline
- **Deterministic Generation**: All model calls run at `temperature=0` to guarantee reproducible outputs.
- **Strict Post-LLM Validator**: Every composed message is parsed and checked before sending. If a message contains raw URLs, multiple question marks, misplaced CTAs, or ungrounded numbers, the validator flags it for a single-pass repair or safe fallback.
- **Latency & Concurrency**: Triggers in `/v1/tick` are evaluated in parallel using a non-blocking worker pool with a strict internal deadline, staying well under the 30-second budget.
- **Multi-Turn Conversation Handlers**: Detects auto-reply loops, handles hostile complaints with graceful termination, redirects off-topic questions, and switches immediately to action mode when a merchant commits.

## 2. Key Tradeoffs

- **Parallel Worker Pool vs. Sequential Execution**: Processing tick triggers concurrently allows evaluating multiple merchant opportunities in 2–4 seconds instead of sequentially timing out.
- **Single-Pass Repair vs. Infinite Retries**: If validation catches a formatting or fact error, we retry once with targeted feedback. If it fails a second time, Vera falls back to a deterministic, context-grounded template to guarantee zero hallucinations and zero latency spikes.

## 3. URL Policy Decision

While some product guidelines mention links, WhatsApp Business and Meta template policies strictly penalize or reject unsolicited raw URLs in initial outreach copy. To keep deliverability high and avoid delivery penalties, **Vera never outputs raw URLs in the message body**. Whenever an external resource or CDE webinar is referenced, Vera describes it clearly in words and offers to share details upon merchant reply.

## 4. What Additional Context Would Have Helped

1. **Real-time Inventory & Slot Feeds**: Live seat availability for salons, gyms, and dental chairs would allow auto-booking exact slots directly in the chat thread.
2. **Historical Reply Rates**: Tracking which trigger types each specific merchant replies to most frequently would allow adaptive suppression weighting.
3. **Margin & COGS Data**: Knowing profit margins on specific dishes or pharmacy items would let Vera prioritize the highest-margin offers during demand surges.

## 5. Running the Service

From the project root directory:
```bash
uvicorn submission.bot:app --host 0.0.0.0 --port 8080 --reload
```

For production / Render deployment:
```bash
uvicorn submission.bot:app --host 0.0.0.0 --port $PORT
```

*Note: Hackathon dates and logistics are pending official confirmation from magicpin per challenge brief §14.*
