"""Durable owner-only records for the Admin Diagnostic Console.

The store uses the existing AIMS/Vault collection boundary. It is not a
second memory authority and never promotes diagnostic conversation into CALI
personal memory or governance data.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.vault_client import vault_client


COLLECTION = "dock.admin_diagnostic_console"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AdminDiagnosticStore:
    def __init__(self):
        self._lock = threading.RLock()

    def _load(self) -> dict:
        value = vault_client.read(COLLECTION, None)
        if not isinstance(value, dict):
            value = {}
        value.setdefault("sessions", {})
        value.setdefault("development_log", [])
        value.setdefault("glyph_trace", [])
        return value

    def _save(self, value: dict) -> None:
        vault_client.write(COLLECTION, value, "Admin diagnostic console record appended")

    def create_session(self, owner_id: str) -> dict:
        with self._lock:
            data = self._load()
            now = utc_now()
            session = {
                "session_id": str(uuid.uuid4()),
                "owner_id": owner_id,
                "runtime_session_id": None,
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "development_event_ids": [],
            }
            data["sessions"][session["session_id"]] = session
            self._trace(data, session, "message_session_created", "success", "dock_station")
            self._save(data)
            return dict(session)

    def list_sessions(self, owner_id: str) -> list[dict]:
        with self._lock:
            data = self._load()
            sessions = [s for s in data["sessions"].values() if s.get("owner_id") == owner_id]
            return sorted((self._summary(s) for s in sessions), key=lambda item: item["updated_at"], reverse=True)

    def get_session(self, session_id: str, owner_id: str) -> dict | None:
        with self._lock:
            session = self._load()["sessions"].get(session_id)
            if not session or session.get("owner_id") != owner_id:
                return None
            return json.loads(json.dumps(session))

    def set_runtime_session(self, session_id: str, owner_id: str, runtime_session_id: str) -> dict:
        with self._lock:
            data = self._load()
            session = self._owned(data, session_id, owner_id)
            session["runtime_session_id"] = runtime_session_id
            session["updated_at"] = utc_now()
            self._save(data)
            return dict(session)

    def append_message(self, session_id: str, owner_id: str, message: dict) -> dict:
        with self._lock:
            data = self._load()
            session = self._owned(data, session_id, owner_id)
            record = {"message_id": str(uuid.uuid4()), "sequence": len(session["messages"]) + 1,
                      "created_at": utc_now(), **message}
            session["messages"].append(record)
            session["updated_at"] = record["created_at"]
            self._save(data)
            return record

    def append_development_event(self, session_id: str, owner_id: str, event: dict) -> dict:
        with self._lock:
            data = self._load()
            session = self._owned(data, session_id, owner_id)
            record = {"event_id": str(uuid.uuid4()), "created_at": utc_now(),
                      "session_id": session_id, "verification_status": "observed", **event}
            data["development_log"].append(record)
            session["development_event_ids"].append(record["event_id"])
            session["updated_at"] = record["created_at"]
            self._save(data)
            return record

    def append_trace(self, session_id: str, owner_id: str, event: dict) -> dict:
        with self._lock:
            data = self._load()
            session = self._owned(data, session_id, owner_id)
            record = {"trace_id": str(uuid.uuid4()), "event_id": str(uuid.uuid4()),
                      "session_id": session_id, "timestamp": utc_now(),
                      "producer": "dock_station.admin_diagnostic_console", **event}
            data["glyph_trace"].append(record)
            session["updated_at"] = record["timestamp"]
            self._save(data)
            return record

    def development_log(self, session_id: str, owner_id: str) -> list[dict]:
        with self._lock:
            data = self._load()
            session = self._owned(data, session_id, owner_id)
            ids = set(session.get("development_event_ids", []))
            return [item for item in data["development_log"] if item.get("event_id") in ids]

    def glyph_trace(self, session_id: str, owner_id: str) -> list[dict]:
        with self._lock:
            data = self._load()
            self._owned(data, session_id, owner_id)
            return [item for item in data["glyph_trace"] if item.get("session_id") == session_id]

    def _owned(self, data: dict, session_id: str, owner_id: str) -> dict:
        session = data["sessions"].get(session_id)
        if not session or session.get("owner_id") != owner_id:
            raise KeyError(session_id)
        return session

    @staticmethod
    def _summary(session: dict) -> dict:
        return {key: session.get(key) for key in ("session_id", "created_at", "updated_at", "runtime_session_id")}

    @staticmethod
    def _trace(data: dict, session: dict, event_type: str, status: str, actor: str, **extra) -> None:
        data["glyph_trace"].append({
            "trace_id": str(uuid.uuid4()), "event_id": str(uuid.uuid4()),
            "session_id": session["session_id"], "timestamp": utc_now(),
            "event_type": event_type, "producer": "dock_station.admin_diagnostic_console",
            "actor": actor, "status": status, **extra,
        })


admin_diagnostic_store = AdminDiagnosticStore()
