# Richpanel support docs

Help-center drafts for **Tuftingshop**, built from Richpanel ticket themes (Aug 2025–Aug 2026) and product pages.

| File | Purpose |
| --- | --- |
| [FAQ.md](FAQ.md) | Short customer FAQ (shipping, orders, returns, customs) |
| [BEGINNER-QA.md](BEGINNER-QA.md) | Product & beginner Q&A (kits, guns, cloth, finishing) |
| [TUFTINGSHOP_FAQ.md](TUFTINGSHOP_FAQ.md) | Longer FAQ with more detail and internal source notes |

Review before publishing to the storefront.

---

## Support auto-respond agent

Local FastAPI app that ingests Richpanel email tickets, drafts replies with Claude (grounded in the FAQ files above + approved memory), and shows them in a browser dashboard for edit / approve / reject. On **Approve & send**, the final text is posted to Richpanel (or simulated when dry-run is on).

Design spec: [docs/superpowers/specs/2026-08-06-support-auto-respond-agent-design.md](docs/superpowers/specs/2026-08-06-support-auto-respond-agent-design.md)

### Requirements

- Python 3.11+
- Richpanel API token and Anthropic API key

### Install

```bash
pip install -e ".[dev]"
```

### Configuration

Copy the example env file and fill in secrets:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `RICHPANEL_API_TOKEN` | Richpanel API access |
| `ANTHROPIC_API_KEY` | Claude draft generation |
| `DRY_RUN` | `true` (default) — Approve simulates send (`sent_simulated`); set `false` only when ready for live Richpanel sends |
| `HOST` | Bind address (default `127.0.0.1`) |
| `PORT` | HTTP port (default `8788`) |
| `DATABASE_PATH` | SQLite file (default `data/support_agent.db`) |
| `SYNC_INTERVAL_SECONDS` | Background ingest interval (default `180`) |

Other optional settings are documented in `.env.example`.

### Run

**1. Bootstrap approved memory** (one-time; pulls closed tickets and seeds similar-answer retrieval):

```bash
python -m app bootstrap-memory
python -m app bootstrap-memory --start 2025-08-01 --end 2026-08-06
```

Defaults to the last 90 days when `--start` / `--end` are omitted.

**2. Start the server** (API, dashboard, and background sync):

```bash
python -m app serve
```

Open **http://127.0.0.1:8788** — review queue on the left, transcript in the center, draft editor on the right. Use **Sync now** in the header to pull open tickets immediately.

### Dry-run vs live send

- **`DRY_RUN=true`** (default): **Approve & send** writes approved memory, updates audit log, and marks the draft `sent_simulated` — **no** Richpanel `send_message` call.
- **`DRY_RUN=false`**: Approve posts the final reply to Richpanel and marks the draft `sent`.

Keep dry-run enabled until you have manually verified behavior on real tickets.

### Safety

- **No automatic send** — only human **Approve & send** triggers outbound messages.
- **Dry-run by default** — first tests should stay in `DRY_RUN=true`.
- **Secrets in `.env` only** — never commit API keys or tokens.
- **Send guard** — if a newer agent reply appeared in Richpanel since the draft was created, send is blocked and the draft stays for review.
- **Localhost only** — default bind is `127.0.0.1`; do not expose without adding auth.
- On API or LLM errors, drafts remain in `needs_review` or `error` with a visible message.

### End-to-end dry-run checklist

Use this before setting `DRY_RUN=false`:

1. [ ] Copy `.env.example` → `.env`; set `RICHPANEL_API_TOKEN`, `ANTHROPIC_API_KEY`; confirm `DRY_RUN=true`.
2. [ ] `pip install -e ".[dev]"` and `python -m pytest -v` — all tests pass.
3. [ ] `python -m app bootstrap-memory` — imports historic approved replies (check console count).
4. [ ] `python -m app serve` — open http://127.0.0.1:8788; header shows dry-run enabled.
5. [ ] Click **Sync now** — open email tickets appear in the queue with drafts (`needs_review`).
6. [ ] Select a ticket — transcript loads; edit draft text; **Save edit** persists without sending.
7. [ ] **Regenerate** with a short instruction — new draft appears; status stays `needs_review`.
8. [ ] **Approve & send** — draft moves to `sent_simulated`; no customer message in Richpanel; approved memory and audit log updated.
9. [ ] **Reject** or **Skip** on another draft — no send, no memory write.
10. [ ] Repeat Approve on ≥5 real open tickets in dry-run; only then set `DRY_RUN=false` for live sends.

### Tests

```bash
python -m pytest -v
```
