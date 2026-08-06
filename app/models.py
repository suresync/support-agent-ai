SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    conversation_no TEXT,
    subject TEXT,
    status TEXT,
    channel TEXT,
    customer_email TEXT,
    customer_name TEXT,
    language TEXT,
    last_customer_message_at TEXT,
    updated_at TEXT,
    raw_snapshot_json TEXT
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    status TEXT NOT NULL CHECK (
        status IN (
            'pending_draft',
            'needs_review',
            'sending',
            'sent',
            'sent_simulated',
            'rejected',
            'skipped',
            'error'
        )
    ),
    draft_text TEXT,
    edited_text TEXT,
    internal_note TEXT,
    confidence REAL,
    model TEXT,
    prompt_version TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS approved_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id),
    customer_question_summary TEXT NOT NULL,
    final_reply TEXT NOT NULL,
    language TEXT,
    theme_tags TEXT,
    embedding BLOB,
    source TEXT NOT NULL CHECK (source IN ('historic', 'approved_live')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    action TEXT NOT NULL,
    conversation_id TEXT,
    draft_id TEXT,
    detail_json TEXT
);
"""
