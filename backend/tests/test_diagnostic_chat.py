import asyncio
import unittest
from unittest.mock import patch

from app.routers import diagnostics
from app.routers.diagnostics import DiagnosticChatRequest


class FakeDiagnosticStore:
    def __init__(self):
        self.session = {
            "session_id": "admin-session",
            "owner_id": "owner@example.com",
            "runtime_session_id": None,
            "created_at": "now",
            "updated_at": "now",
            "messages": [],
            "development_event_ids": [],
        }

    def get_session(self, session_id, owner_id):
        return self.session if session_id == self.session["session_id"] and owner_id == self.session["owner_id"] else None

    def create_session(self, owner_id):
        self.session["owner_id"] = owner_id
        return dict(self.session)

    def set_runtime_session(self, session_id, owner_id, runtime_session_id):
        self.session["runtime_session_id"] = runtime_session_id
        return dict(self.session)

    def append_trace(self, *args, **kwargs):
        return {"trace_id": "trace"}

    def append_development_event(self, *args, **kwargs):
        return {"event_id": "event"}

    def append_message(self, session_id, owner_id, message):
        record = {"message_id": "message", **message}
        self.session["messages"].append(record)
        return record


class DiagnosticChatTests(unittest.TestCase):
    def test_chat_uses_existing_reasoning_without_speech(self):
        store = FakeDiagnosticStore()
        calls = []

        def gateway(route, payload=None):
            calls.append((route, payload))
            if route == "/sessions":
                return {"session_id": "runtime-session"}
            return {"text": "The attached evidence is measured, but no live recovery test is recorded.",
                    "context": {"model_id": "nvidia/test-model"},
                    "inference_context": {"provider": "nvidia"}}

        with patch.object(diagnostics, "admin_diagnostic_store", store), patch.object(diagnostics.vault_client, "call", side_effect=gateway):
            result = asyncio.run(diagnostics.diagnostic_chat(
                DiagnosticChatRequest(message="Analyze the microphone evidence.", section="Speech and hearing",
                                      captured_at="2026-11-22T23:00:00Z", measurements={"microphone": {"value": True}}),
                owner={"sub": "owner@example.com"},
            ))

        self.assertEqual(result["session_id"], "admin-session")
        self.assertEqual(result["provider"], "nvidia")
        conversation = next(payload for route, payload in calls if route == "/conversation")
        self.assertFalse(conversation["speak"])
        self.assertIn("Speech and hearing", conversation["text"])
        self.assertIn("Analyze the microphone evidence", conversation["text"])


if __name__ == "__main__":
    unittest.main()
