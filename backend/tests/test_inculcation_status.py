import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security import create_access_token
from app.routers import diagnostics


class ProfessionalStatusTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(diagnostics.router)
        self.client = TestClient(app)

    def test_anonymous_request_does_not_read_vault(self):
        with patch.object(diagnostics.vault_client, "call") as call:
            self.assertEqual(self.client.get("/diagnostics/inculcation").status_code, 401)
        call.assert_not_called()

    def test_authenticated_request_uses_existing_client_without_write_payload(self):
        token = create_access_token({"sub": "fixture-owner", "role": "owner"})
        with patch.object(diagnostics.vault_client, "call", return_value={"validated": True, "execution_authority": False}) as call:
            result = self.client.get("/diagnostics/inculcation", headers={"Authorization": "Bearer " + token})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["execution_authority"])
        call.assert_called_once_with("/inculcation/status")

    def test_update_method_is_not_exposed(self):
        self.assertEqual(self.client.post("/diagnostics/inculcation", json={"version": "invented"}).status_code, 405)


if __name__ == "__main__":
    unittest.main()
