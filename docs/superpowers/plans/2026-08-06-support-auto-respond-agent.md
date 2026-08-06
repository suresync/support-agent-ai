# Support Auto-Respond Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI review-queue app that syncs Richpanel email tickets, drafts Claude replies grounded in FAQ + approved memory, lets an operator edit/approve in a browser dashboard, and sends approved replies via Richpanel.

**Architecture:** Single Python package `app/` with SQLite persistence, background sync loop, Claude draft agent, local sentence-transformers embeddings for memory retrieval, and a one-page dashboard served by FastAPI. Approve & send is the only path that calls Richpanel `send_message`.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLite (stdlib), Anthropic SDK, sentence-transformers, numpy, httpx, pytest, Jinja2 (or static HTML+JS).

## Global Constraints

- No automatic send — only human **Approve & send** (or dry-run simulated send).
- Reply language matches the customer’s last message.
- Learning v1 = approved memory retrieval only (no fine-tuning).
- Secrets only in `.env` (gitignored); never commit tokens.
- Bind dashboard to `127.0.0.1` only by default.
- Follow design spec: `docs/superpowers/specs/2026-08-06-support-auto-respond-agent-design.md`.
- TDD: write failing test → implement → pass → commit per task.
- Windows-friendly commands (PowerShell); use `python -m pytest`.

---

## File structure

```text
app/
  __init__.py
  __main__.py          # python -m app → CLI
  config.py            # settings from env
  db.py                # SQLite schema + helpers
  models.py            # dataclasses / row mappers
  richpanel_client.py  # HTTP client (list/get/send)
  language.py          # detect reply language
  auto_reply.py        # filter generic auto-replies
  embeddings.py        # encode text → float32 vector
  memory.py            # approved_memory CRUD + similarity search
  faq.py               # load FAQ.md / BEGINNER-QA.md chunks
  draft_agent.py       # Claude draft generation
  ingest.py            # sync open tickets + enqueue drafts
  bootstrap.py         # historic closed-ticket memory seed
  sender.py            # send guard + Richpanel send + memory write
  api.py               # FastAPI routes for dashboard
  sync_loop.py         # background periodic ingest
  static/
    dashboard.html     # single-page UI
    dashboard.css
    dashboard.js
tests/
  test_language.py
  test_auto_reply.py
  test_memory.py
  test_send_guard.py
  test_draft_agent.py
  test_api_approve.py
  conftest.py
.env.example
pyproject.toml
README.md              # update with run instructions
```

---

### Task 1: Project scaffold + config

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/__main__.py`
- Create: `app/config.py`
- Create: `.env.example`
- Modify: `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` dataclass from `app.config.get_settings()` with fields `anthropic_api_key`, `richpanel_api_token`, `richpanel_base_url`, `database_path`, `dry_run`, `sync_interval_seconds`, `host`, `port`, `embedding_model_name`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import os
from app.config import get_settings

def test_get_settings_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("RICHPANEL_API_TOKEN", "rp-test")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DRY_RUN", "true")
    s = get_settings()
    assert s.anthropic_api_key == "sk-test"
    assert s.richpanel_api_token == "rp-test"
    assert s.dry_run is True
    assert s.host == "127.0.0.1"
    assert s.port == 8788
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 3: Implement scaffold**

`pyproject.toml`:

```toml
[project]
name = "support-agent-ai"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.32.0",
  "httpx>=0.27.0",
  "anthropic>=0.39.0",
  "numpy>=2.0.0",
  "sentence-transformers>=3.0.0",
  "python-dotenv>=1.0.0",
  "pydantic-settings>=2.6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`app/config.py`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    anthropic_api_key: str = ""
    richpanel_api_token: str = ""
    richpanel_base_url: str = "https://api.richpanel.com"
    database_path: str = "data/support_agent.db"
    dry_run: bool = True
    sync_interval_seconds: int = 180
    host: str = "127.0.0.1"
    port: int = 8788
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    anthropic_model: str = "claude-sonnet-4-20250514"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`.env.example`:

```env
ANTHROPIC_API_KEY=
RICHPANEL_API_TOKEN=
RICHPANEL_BASE_URL=https://api.richpanel.com
DATABASE_PATH=data/support_agent.db
DRY_RUN=true
SYNC_INTERVAL_SECONDS=180
HOST=127.0.0.1
PORT=8788
```

Add to `.gitignore`: `.env`, `data/`, `__pycache__/`, `.venv/`, `*.db`

`app/__main__.py`:

```python
def main() -> None:
    import sys
    print("Commands: serve | bootstrap-memory — implement in later tasks")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml app tests/test_config.py .env.example .gitignore
git commit -m "feat: scaffold app package and settings"
```

---

### Task 2: SQLite schema + db helpers

**Files:**
- Create: `app/db.py`
- Create: `app/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `init_db(path) -> sqlite3.Connection`; `get_connection(path)`; tables `conversations`, `drafts`, `approved_memory`, `audit_log` as in the design spec

- [ ] **Step 1: Write failing test**

```python
# tests/test_db.py
from app.db import init_db, get_connection

def test_init_db_creates_tables(tmp_path):
    path = tmp_path / "t.db"
    init_db(str(path))
    conn = get_connection(str(path))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"conversations", "drafts", "approved_memory", "audit_log"} <= tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `app/db.py` and `app/models.py`**

Create tables matching the design spec exactly (`drafts.status` includes `sent_simulated`; `drafts.internal_note`; `approved_memory.embedding BLOB`). Include helper `log_audit(conn, action, conversation_id=None, draft_id=None, detail=None)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db.py app/models.py tests/test_db.py
git commit -m "feat: add SQLite schema for conversations, drafts, memory"
```

---

### Task 3: Language detection + auto-reply filter

**Files:**
- Create: `app/language.py`
- Create: `app/auto_reply.py`
- Test: `tests/test_language.py`
- Test: `tests/test_auto_reply.py`

**Interfaces:**
- Produces: `detect_language(text: str) -> str` (ISO-ish: `en`, `nl`, `de`, `fr`, `es`, `other`)
- Produces: `is_generic_auto_reply(text: str) -> bool`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_language.py
from app.language import detect_language

def test_detect_dutch():
    assert detect_language("Beste, ik wil mijn bestelling annuleren. Groetjes") == "nl"

def test_detect_english():
    assert detect_language("Hi, where is my order #12345 tracking please?") == "en"

# tests/test_auto_reply.py
from app.auto_reply import is_generic_auto_reply

def test_flags_hi_autoresponder():
    text = 'Did you mean to check the status of your order?\nIf this auto-response did not answer your question, just reply to this email with a "hi".'
    assert is_generic_auto_reply(text) is True

def test_allows_real_agent_reply():
    text = "Hi Saila,\nI’m sorry the cotton cloth was missing. We’ll reship it today."
    assert is_generic_auto_reply(text) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_language.py tests/test_auto_reply.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement**

Use lightweight heuristics (keyword / stopword counts) for language — no extra API. Auto-reply: match phrases `reply to this email with a "hi"`, `Did you mean to check the status`, `auto-response`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_language.py tests/test_auto_reply.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/language.py app/auto_reply.py tests/test_language.py tests/test_auto_reply.py
git commit -m "feat: add language detection and auto-reply filtering"
```

---

### Task 4: Embeddings + approved memory retrieval

**Files:**
- Create: `app/embeddings.py`
- Create: `app/memory.py`
- Test: `tests/test_memory.py`
- Modify: `tests/conftest.py` (shared tmp db)

**Interfaces:**
- Produces: `embed_texts(texts: list[str], model_name: str | None = None) -> list[bytes]` (float32 little-endian blobs)
- Produces: `add_memory(conn, *, question_summary, final_reply, language, theme_tags, source, conversation_id=None) -> str`
- Produces: `search_similar(conn, query: str, *, language: str | None, limit: int = 5) -> list[MemoryHit]`

- [ ] **Step 1: Write failing test**

```python
# tests/test_memory.py
from app.db import init_db, get_connection
from app.memory import add_memory, search_similar

def test_search_similar_returns_related_memory(tmp_path, monkeypatch):
    # Use a deterministic stub embedding in tests to avoid downloading models
    from app import embeddings
    def fake_embed(texts, model_name=None):
        import numpy as np
        out = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            v[hash(t.lower().split()[0]) % 8] = 1.0
            out.append(v.tobytes())
        return out
    monkeypatch.setattr(embeddings, "embed_texts", fake_embed)

    path = str(tmp_path / "t.db")
    init_db(path)
    conn = get_connection(path)
    add_memory(conn, question_summary="missing yarn cones from order",
               final_reply="We can reship or refund the missing cones.",
               language="en", theme_tags=["missing-items"], source="historic")
    add_memory(conn, question_summary="how to start tufting beginner kit",
               final_reply="The AK DUO starter kit is a good choice.",
               language="en", theme_tags=["beginner"], source="historic")
    hits = search_similar(conn, "my package is missing three yarn cones", language="en", limit=2)
    assert hits[0].final_reply.startswith("We can reship")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `embeddings.py` + `memory.py`**

`embed_texts` loads sentence-transformers lazily (real path). Cosine similarity over all memories filtered optionally by language; return top-K `MemoryHit(id, question_summary, final_reply, score)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/embeddings.py app/memory.py tests/test_memory.py tests/conftest.py
git commit -m "feat: approved memory store with similarity search"
```

---

### Task 5: FAQ loader

**Files:**
- Create: `app/faq.py`
- Test: `tests/test_faq.py`

**Interfaces:**
- Produces: `load_faq_chunks(repo_root: str | Path) -> list[str]` reading `FAQ.md`, `BEGINNER-QA.md`, optionally `TUFTINGSHOP_FAQ.md`, split on `##` / `###` headings

- [ ] **Step 1: Write failing test** for non-empty chunks from repo root  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement**  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: load FAQ markdown chunks for draft context`

---

### Task 6: Richpanel client (mockable)

**Files:**
- Create: `app/richpanel_client.py`
- Test: `tests/test_richpanel_client.py`

**Interfaces:**
- Produces: class `RichpanelClient` with:
  - `list_conversations(*, status: str, start_date: str, end_date: str, page: int = 1, per_page: int = 50) -> list[dict]`
  - `get_conversation(conversation_id: str) -> dict`
  - `send_message(conversation_id: str, body: str) -> dict`
- Auth header: `Authorization: Bearer {token}` (adjust if Richpanel docs differ during implementation; keep header construction in one place)

- [ ] **Step 1: Write failing test** using `httpx.MockTransport` that asserts GET/POST paths and returns fixture JSON  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement httpx client**  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: add Richpanel HTTP client`

**Note:** If live API paths differ from assumptions (`/v1/conversations`, etc.), fix paths in this task only after a single live smoke call with the real token; keep interface stable.

---

### Task 7: Send guard + sender

**Files:**
- Create: `app/sender.py`
- Test: `tests/test_send_guard.py`

**Interfaces:**
- Produces: `approve_and_send(conn, client, draft_id: str, *, dry_run: bool) -> SendResult`
- `SendResult(ok: bool, status: str, error: str | None)`
- Behavior: load draft + conversation; re-fetch conversation; if newer outbound agent/operator message since `draft.created_at`, return error and do not send; else send (or simulate); set status `sent` / `sent_simulated`; write `approved_memory` from final text; audit log

- [ ] **Step 1: Write failing tests**

```python
def test_send_guard_blocks_when_newer_outbound(monkeypatch, tmp_path):
    ...

def test_dry_run_does_not_call_send(monkeypatch, tmp_path):
    ...

def test_approve_writes_memory(monkeypatch, tmp_path):
    ...
```

- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement**  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: approve-and-send with send guard and dry-run`

---

### Task 8: Draft agent (Claude)

**Files:**
- Create: `app/draft_agent.py`
- Test: `tests/test_draft_agent.py`

**Interfaces:**
- Produces: `generate_draft(*, transcript: str, language: str, faq_chunks: list[str], memories: list[MemoryHit], instruction: str | None, settings: Settings) -> DraftResult`
- `DraftResult(text: str, confidence: float, internal_note: str | None)`

- [ ] **Step 1: Write failing test** with monkeypatched Anthropic client returning fixed JSON/text  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement** system prompt with hard constraints from the design spec; user payload includes transcript, FAQ excerpts, similar memories, language, optional instruction; parse reply + confidence + internal_note  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: Claude draft agent grounded in FAQ and memory`

---

### Task 9: Ingest + draft enqueue

**Files:**
- Create: `app/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces: `sync_once(conn, client, settings) -> SyncStats`  
  - lists OPEN email conversations updated recently  
  - upserts `conversations`  
  - if no active `needs_review` draft or customer message newer than draft → create draft via draft_agent + memory search + faq  

- [ ] **Step 1: Write failing test** with fake client returning one open ticket; assert draft row `needs_review`  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement**  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: sync open tickets and enqueue drafts`

---

### Task 10: Historic bootstrap

**Files:**
- Create: `app/bootstrap.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Produces: `bootstrap_memory(conn, client, *, start_date: str, end_date: str, settings) -> int` (count inserted)  
  - pages CLOSED conversations  
  - skips generic auto-replies  
  - for each human agent reply, summarize question (Claude or heuristic first-customer-message truncate) and `add_memory(..., source="historic")`

- [ ] **Step 1: Write failing test** with fixtures: one auto-reply-only thread (skipped), one real agent reply (inserted)  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement** (v1 question_summary = truncated last customer message before agent reply; optional Claude summarize later)  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: bootstrap approved memory from historic tickets`

---

### Task 11: FastAPI routes + sync loop + CLI

**Files:**
- Create: `app/api.py`
- Create: `app/sync_loop.py`
- Modify: `app/__main__.py`
- Test: `tests/test_api_approve.py`

**Interfaces:**
- Produces routes:
  - `GET /api/queue` → needs_review drafts + conversation summary  
  - `GET /api/drafts/{id}` → draft + transcript  
  - `POST /api/drafts/{id}/save` `{text}`  
  - `POST /api/drafts/{id}/approve` `{text?}` → sender  
  - `POST /api/drafts/{id}/reject` `{reason?}`  
  - `POST /api/drafts/{id}/skip`  
  - `POST /api/drafts/{id}/regenerate` `{instruction?}`  
  - `POST /api/sync`  
  - `GET /` → dashboard HTML  
- CLI: `python -m app serve`, `python -m app bootstrap-memory [--start YYYY-MM-DD] [--end YYYY-MM-DD]`

- [ ] **Step 1: Write failing API test** using `TestClient`: create draft in db, POST approve with dry_run, expect `sent_simulated`  
- [ ] **Step 2: Run to fail**  
- [ ] **Step 3: Implement API + CLI + background `sync_loop` started on serve**  
- [ ] **Step 4: Run to pass**  
- [ ] **Step 5: Commit** `feat: API routes, CLI serve/bootstrap, background sync`

---

### Task 12: Dashboard UI

**Files:**
- Create: `app/static/dashboard.html`
- Create: `app/static/dashboard.css`
- Create: `app/static/dashboard.js`

**Interfaces:**
- Consumes: Task 11 JSON API  
- Produces: single-page UI — left queue, center transcript, right editor with Approve & send / Save / Reject / Skip / Regenerate; header Sync now + dry-run indicator

- [ ] **Step 1: Manual structure check** — implement HTML/CSS/JS wired to API (no screenshot automation required)  
- [ ] **Step 2: Start server in dry-run and verify queue loads**  

Run: `python -m app serve` then open `http://127.0.0.1:8788`  
Expected: empty or fixture queue renders without JS errors

- [ ] **Step 3: Commit**

```bash
git add app/static
git commit -m "feat: local review dashboard UI"
```

---

### Task 13: README + end-to-end dry-run checklist

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README** with: install, `.env`, `bootstrap-memory`, `serve`, dry-run vs live (`DRY_RUN=false`), safety notes, link to design spec  
- [ ] **Step 2: Run full unit suite**

Run: `python -m pytest -v`  
Expected: all PASS

- [ ] **Step 3: Commit + push**

```bash
git add README.md
git commit -m "docs: explain how to run the support auto-respond agent"
git push
```

---

## Spec coverage check

| Spec requirement | Task |
| --- | --- |
| Ingest open tickets | 9 |
| Historic bootstrap | 10 |
| Claude drafts + FAQ + memory | 5, 4, 8 |
| Dashboard edit/approve/reject | 11, 12 |
| Approved memory learning | 4, 7 |
| Send on approve via Richpanel | 6, 7 |
| Match customer language | 3, 8 |
| Send guard / dry-run / audit | 2, 7 |
| Localhost FastAPI app | 1, 11 |
| Tests | each task |

## Placeholder / consistency review

- No TBD left in tasks.  
- Status enum includes `sent_simulated` consistently.  
- `approve_and_send` is the single send entry point used by API.  
- Richpanel URL paths may need one live adjustment in Task 6 without changing method names.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-06-support-auto-respond-agent.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
