# Support Auto-Respond Agent — Design Spec

**Date:** 2026-08-06  
**Repo:** `suresync/support-agent-ai`  
**Status:** Draft for implementation planning (awaiting user review)

## Goal

Build a **local** system that:

1. Ingests historic and live Richpanel email conversations for Tuftingshop  
2. Drafts customer replies using a cloud LLM (Claude) grounded in FAQ docs + similar past approved answers  
3. Shows drafts in a **local dashboard** for edit / approve / reject  
4. **Learns** from approved (and edited) replies via approved-memory retrieval (no fine-tuning in v1)  
5. On approve, **sends the reply immediately** through Richpanel  

## Decisions (locked)

| Topic | Choice |
| --- | --- |
| Workflow | Review queue — drafts wait for human approval |
| LLM | Cloud (Claude API) |
| On Approve | Send immediately via Richpanel (`send_message`) |
| Learning (v1) | Approved memory: store final reply + context; retrieve similar cases for new drafts |
| Reply language | Match the customer’s last message language |
| Architecture style | Single local Python (FastAPI) app + SQLite + browser dashboard |
| Hosting | Local machine only (no cloud DB) |

## Architecture

One local Python process:

```text
Richpanel ──sync──► Ingest worker
                         │
                         ▼
                   SQLite (tickets, drafts, approved memory, audit log)
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         Draft agent   Dashboard   Sender
         (Claude +     (browser:   (Approve →
          FAQ +         edit /      Richpanel
          similar       approve /   send_message)
          memory)       reject)
```

### Components

1. **Ingest worker** — periodically fetches new/open email conversations from Richpanel; stores compact snapshots (id, conversation number, subject, customer, messages, tags, timestamps).  
2. **Draft agent** — for conversations without an active draft (or when customer sent a new message), generates a reply draft in the customer’s language using Claude, FAQ markdown, and top-K similar approved memories.  
3. **Dashboard** — local web UI for the review queue.  
4. **Sender** — on Approve & send only: posts the final text to Richpanel and records success/failure.  
5. **Approved memory store** — persists approved/edited Q→A pairs for future retrieval.  

Out of scope for v1: mobile app, multi-user auth, fine-tuning, automatic send without approval, non-email channels.

## Data model (SQLite)

### `conversations`
- `id` (Richpanel conversation id, PK)  
- `conversation_no`, `subject`, `status`, `channel`  
- `customer_email`, `customer_name`  
- `language` (detected)  
- `last_customer_message_at`, `updated_at`  
- `raw_snapshot_json` (compact transcript cache)

### `drafts`
- `id` (local UUID, PK)  
- `conversation_id` (FK)  
- `status`: `pending_draft` | `needs_review` | `sent` | `sent_simulated` | `rejected` | `skipped` | `error`  
- `draft_text`, `edited_text` (nullable until user edits)  
- `internal_note` (nullable; dashboard-only, never sent)  
- `confidence` (0–1, model self-estimate or heuristic)  
- `model`, `prompt_version`  
- `error_message` (nullable)  
- `created_at`, `updated_at`, `reviewed_at`, `sent_at`

### `approved_memory`
- `id` (PK)  
- `conversation_id` (nullable for historic bootstrap)  
- `customer_question_summary`  
- `final_reply`  
- `language`, `theme_tags` (JSON)  
- `embedding` (float32 blob; cosine similarity in-process for v1 — no external vector DB)  
- `source`: `historic` | `approved_live`  
- `created_at`

### `audit_log`
- `id`, `ts`, `action` (`approve_send` | `reject` | `regenerate` | `sync` | …)  
- `conversation_id`, `draft_id`, `detail_json`

## Ticket / draft lifecycle

```text
NEW/OPEN ticket in Richpanel
        │
        ▼
Ingest (every N minutes, default 2–5) → store snapshot
        │
        ▼
Draft agent → status: needs_review
        │
        ▼
Dashboard review
        │
   ┌────┴────┬────────────┐
   ▼         ▼            ▼
Edit      Approve & send     Reject / Skip
   │         │                  │
   │         ▼                  ▼
   │    Send via RP        mark rejected/skipped
   │    status: sent       (NO write to approved_memory)
   │         │
   └────► only on Approve: upsert approved_memory
          (final text = edited_text if set else draft_text)
```

**Regenerate:** user may add a short instruction; agent rewrites draft; status stays `needs_review`.

**Customer wrote again while draft pending:** ingest detects newer customer message → mark existing draft `skipped` (stale) → create a new draft.

**Skip vs Reject:** both leave the queue without sending and without writing memory. Reject stores an optional reason in `audit_log` for later analysis; Skip is silent.

## Historic bootstrap

One-time (and optionally nightly) job:

1. Pull closed email conversations for the past ~12 months (paginated via Richpanel).  
2. Extract Q/A pairs where a **human agent** reply exists (exclude generic auto-replies that only say “reply hi”).  
3. Summarize customer ask + store final agent reply into `approved_memory` with `source=historic`.  
4. Seed embeddings for retrieval.

Existing markdown FAQ files (`FAQ.md`, `BEGINNER-QA.md`, `TUFTINGSHOP_FAQ.md`) are always available as static knowledge to the draft agent.

## Draft agent behavior

**Inputs:** conversation transcript (cleaned), detected language, FAQ chunks, top-K similar memories, optional regenerate instruction.

**Output:** draft reply text + confidence + optional internal note (shown only in dashboard, never sent) e.g. “Verify tracking before promising ship date.”

**Hard constraints (system prompt):**

- Never invent tracking numbers, refund amounts, or stock promises not present in context.  
- Never claim customs are included in shipping.  
- Tufting cloth is cut-to-order and generally non-returnable (per policy).  
- Match customer language.  
- If uncertain, lower confidence and ask the human to verify via internal note.

**LLM:** Anthropic Claude API (model configurable via `.env`).

## Dashboard (v1 single page)

**Left — Queue:** conversations in `needs_review` (and optionally `error`). Show ticket #, subject, language, age, confidence. Filters: all / high confidence / oldest first.

**Center — Ticket:** customer identity + recent transcript. Distinguish customer / agent / auto-reply.

**Right — Draft editor:**

- Editable textarea (starts as model draft)  
- **Approve & send** — send final text via Richpanel; write memory; audit log  
- **Save edit** — persist `edited_text` without sending  
- **Reject** — optional reason in audit log; no send; no memory write  
- **Skip** — leave queue silently; no send; no memory write  
- **Regenerate** — optional instruction field  

**Header:** last sync time, **Sync now** button, dry-run toggle (see Safety).

## Richpanel integration

Python client wrapping Richpanel’s HTTP API (same backend the MCP server uses). Auth for v1: long-lived API access via OAuth refresh token or API key stored in local `.env` / credential file (never committed). Exact auth mechanism is fixed during implementation against Richpanel’s current API docs; the app must support token refresh if OAuth is used.

Required operations:

- List/get conversations (ingest + bootstrap)  
- `send_message` on approve  

Optional (v1 nice-to-have, not blocking): private note for `internal_note`.

**Send guard:** before send, re-fetch conversation; if a newer outbound operator/agent message exists since draft creation, block send and force regenerate/review.

## Safety & errors

- **No automatic send** — human Approve & send only.  
- **Dry-run mode** (config flag): Approve stores memory and marks `sent_simulated` without calling Richpanel (for first manual tests).  
- Secrets only in `.env` (gitignored): `ANTHROPIC_API_KEY`, Richpanel credentials/token path.  
- On Richpanel/Claude failure: keep draft in `needs_review` or `error`; surface message in UI; retry with backoff for sync.  
- Audit every approve/send/reject/regenerate.

## Testing

- Unit: language detection, send-guard, memory retrieval ranking, auto-reply filtering for bootstrap.  
- Integration: mock Richpanel client for approve→send path; mock Claude for draft generation.  
- Manual: dry-run on ≥5 real open tickets before enabling live send.

## Run model (operator)

```bash
# from repo
cp .env.example .env   # fill keys
python -m app bootstrap-memory   # historic once
python -m app serve              # API + UI + background sync
# open http://127.0.0.1:8788
```

Default bind: localhost only.

## Non-goals (v1)

- Multi-agent / role-based dashboard login  
- SMS/social channels  
- Auto-close tickets  
- Fine-tuning or hosted vector DB SaaS  
- Replacing Richpanel UI entirely  

## Success criteria

1. Historic bootstrap loads a usable approved-memory set from past-year tickets.  
2. New open email tickets appear in the queue with a draft within one sync cycle.  
3. Operator can edit and Approve & send; customer receives the message in Richpanel.  
4. A subsequent similar ticket’s draft clearly reuses patterns from the approved memory / FAQ.  
5. Dry-run mode works before first live send.
