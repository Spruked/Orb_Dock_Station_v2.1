import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app


class LiveConversationTests(unittest.TestCase):
    def test_live_endpoint_projects_both_sides_and_evidence(self):
        token = create_access_token({"sub": "owner@orb.system", "role": "owner"})
        payload = {
            "available": True,
            "session_id": "session-live",
            "turns": [{
                "turn_id": "turn-1",
                "transcript": [
                    {"speaker": "owner", "text": "Hey CALI"},
                    {"speaker": "cali", "text": "Hello, Bryan."},
                ],
                "context": {"session_id": "session-live"},
                "evidence": {"recalled_atom_ids": ["atom-1"]},
            }],
        }
        with patch("app.routers.conversations.vault_client.call", return_value=payload):
            response = TestClient(app).get(
                "/conversations/live",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["live"])
        self.assertEqual(body["turns"][0]["transcript"][0]["speaker"], "owner")
        self.assertEqual(body["turns"][0]["transcript"][1]["speaker"], "cali")
        self.assertEqual(body["turns"][0]["evidence"]["recalled_atom_ids"], ["atom-1"])


if __name__ == "__main__":
    unittest.main()
