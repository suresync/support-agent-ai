from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import init_db
from app.draft_agent import generate_draft
from app.faq import load_faq_chunks
from app.ingest import _transcript, sync_once
from app.memory import search_similar
from app.richpanel_client import RichpanelClient
from app.sender import approve_and_send


class TextBody(BaseModel):
    text: str


class ApproveBody(BaseModel):
    text: str | None = None


class ReasonBody(BaseModel):
    reason: str | None = None


class RegenerateBody(BaseModel):
    instruction: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_dict(columns: list[str], row: Any) -> dict[str, Any]:
    return dict(zip(columns, row, strict=True))


def create_app(
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_client = client or RichpanelClient(
        resolved_settings.richpanel_api_token,
        resolved_settings.richpanel_base_url,
    )
    api = FastAPI(title="Richpanel Support Agent")
    api.state.settings = resolved_settings
    api.state.client = resolved_client

    def connection():
        return init_db(resolved_settings.database_path)

    @api.get("/api/queue")
    def queue() -> list[dict[str, Any]]:
        conn = connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    d.id, d.conversation_id, d.status, d.draft_text,
                    d.edited_text, d.internal_note, d.confidence,
                    d.created_at, d.updated_at, c.conversation_no,
                    c.subject, c.customer_email, c.customer_name,
                    c.language, c.last_customer_message_at
                FROM drafts AS d
                JOIN conversations AS c ON c.id = d.conversation_id
                WHERE d.status = 'needs_review'
                ORDER BY d.created_at ASC
                """
            ).fetchall()
            columns = [
                "id", "conversation_id", "status", "draft_text",
                "edited_text", "internal_note", "confidence", "created_at",
                "updated_at", "conversation_no", "subject", "customer_email",
                "customer_name", "language", "last_customer_message_at",
            ]
            return [_row_dict(columns, row) for row in rows]
        finally:
            conn.close()

    @api.get("/api/drafts/{draft_id}")
    def draft_detail(draft_id: str) -> dict[str, Any]:
        conn = connection()
        try:
            row = conn.execute(
                """
                SELECT
                    d.id, d.conversation_id, d.status, d.draft_text,
                    d.edited_text, d.internal_note, d.confidence, d.model,
                    d.prompt_version, d.error_message, d.created_at,
                    d.updated_at, d.reviewed_at, d.sent_at, c.subject,
                    c.customer_email, c.customer_name, c.language,
                    c.raw_snapshot_json
                FROM drafts AS d
                JOIN conversations AS c ON c.id = d.conversation_id
                WHERE d.id = ?
                """,
                (draft_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Draft not found")
            columns = [
                "id", "conversation_id", "status", "draft_text",
                "edited_text", "internal_note", "confidence", "model",
                "prompt_version", "error_message", "created_at", "updated_at",
                "reviewed_at", "sent_at", "subject", "customer_email",
                "customer_name", "language", "raw_snapshot_json",
            ]
            result = _row_dict(columns, row)
            raw = result.pop("raw_snapshot_json")
            try:
                snapshot = json.loads(raw) if raw else {}
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            result["transcript"] = _transcript(snapshot)[0]
            return result
        finally:
            conn.close()

    @api.post("/api/drafts/{draft_id}/save")
    def save_draft(draft_id: str, body: TextBody) -> dict[str, Any]:
        conn = connection()
        try:
            cursor = conn.execute(
                "UPDATE drafts SET edited_text = ?, updated_at = ? WHERE id = ?",
                (body.text, _now(), draft_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(404, "Draft not found")
            conn.commit()
            return {"id": draft_id, "status": "saved", "text": body.text}
        finally:
            conn.close()

    @api.post("/api/drafts/{draft_id}/approve")
    def approve_draft(draft_id: str, body: ApproveBody) -> dict[str, Any]:
        conn = connection()
        try:
            if body.text is not None:
                cursor = conn.execute(
                    "UPDATE drafts SET edited_text = ?, updated_at = ? WHERE id = ?",
                    (body.text, _now(), draft_id),
                )
                if cursor.rowcount == 0:
                    raise HTTPException(404, "Draft not found")
                conn.commit()
            result = approve_and_send(
                conn,
                resolved_client,
                draft_id,
                dry_run=resolved_settings.dry_run,
            )
            if not result.ok:
                status_code = 404 if result.status == "not_found" else 409
                raise HTTPException(status_code, result.error or "Approval failed")
            return asdict(result)
        finally:
            conn.close()

    def set_status(
        draft_id: str,
        status: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        conn = connection()
        try:
            now = _now()
            cursor = conn.execute(
                """
                UPDATE drafts
                SET status = ?, error_message = ?, updated_at = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status, reason, now, now, draft_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(404, "Draft not found")
            conn.commit()
            return {"id": draft_id, "status": status}
        finally:
            conn.close()

    @api.post("/api/drafts/{draft_id}/reject")
    def reject_draft(draft_id: str, body: ReasonBody) -> dict[str, Any]:
        return set_status(draft_id, "rejected", reason=body.reason)

    @api.post("/api/drafts/{draft_id}/skip")
    def skip_draft(draft_id: str) -> dict[str, Any]:
        return set_status(draft_id, "skipped")

    @api.post("/api/drafts/{draft_id}/regenerate")
    def regenerate_draft(
        draft_id: str, body: RegenerateBody
    ) -> dict[str, Any]:
        conn = connection()
        try:
            row = conn.execute(
                """
                SELECT d.conversation_id, c.language, c.raw_snapshot_json, c.subject
                FROM drafts AS d
                JOIN conversations AS c ON c.id = d.conversation_id
                WHERE d.id = ?
                """,
                (draft_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Draft not found")
            _, language, raw_snapshot, subject = row
            try:
                snapshot = json.loads(raw_snapshot) if raw_snapshot else {}
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            transcript = _transcript(snapshot)[0] or subject or ""
            result = generate_draft(
                transcript=transcript,
                language=language or "unknown",
                faq_chunks=load_faq_chunks(Path(__file__).resolve().parent.parent),
                memories=search_similar(
                    conn, transcript, language=language, limit=5
                ),
                instruction=body.instruction,
                settings=resolved_settings,
            )
            conn.execute(
                """
                UPDATE drafts
                SET status = 'needs_review', draft_text = ?, edited_text = NULL,
                    internal_note = ?, confidence = ?, error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    result.text,
                    result.internal_note,
                    result.confidence,
                    _now(),
                    draft_id,
                ),
            )
            conn.commit()
            return {
                "id": draft_id,
                "status": "needs_review",
                "text": result.text,
                "confidence": result.confidence,
                "internal_note": result.internal_note,
            }
        finally:
            conn.close()

    @api.post("/api/sync")
    def sync() -> dict[str, int]:
        conn = connection()
        try:
            return asdict(sync_once(conn, resolved_client, resolved_settings))
        finally:
            conn.close()

    @api.get("/", response_class=HTMLResponse)
    def dashboard():
        dashboard_path = Path(__file__).resolve().parent / "static" / "dashboard.html"
        if dashboard_path.is_file():
            return FileResponse(dashboard_path)
        return HTMLResponse(
            "<!doctype html><html><body><h1>Richpanel Support Agent</h1></body></html>"
        )

    return api


app = create_app()
