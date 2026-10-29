import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import intelligence
from app.models import ModelLane, ModelConfig


class ModelMeasurementsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(intelligence.router)
        app.dependency_overrides[intelligence.get_current_owner] = lambda: {"role": "owner"}
        self.client = TestClient(app)
        self.profile = SimpleNamespace(intelligence=SimpleNamespace(lanes=[
            ModelLane(name="local", config=ModelConfig(model_id="qwen2.5-7b-instruct"))]))

    def test_saved_health_cannot_override_measured_model(self):
        with patch.object(intelligence.profile_service, "get_profile", return_value=self.profile), patch.object(intelligence.vault_client, "call", return_value={"models": ["different-model"], "llm_connected": True}) as call:
            result = self.client.post("/intelligence/fixture/lanes/local/test")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["passed"])
        self.assertIsNone(result.json()["ttf_ms"])
        call.assert_called_once_with("/status")

    def test_matching_runtime_is_measured_without_generation(self):
        with patch.object(intelligence.profile_service, "get_profile", return_value=self.profile), patch.object(intelligence.vault_client, "call", return_value={"models": ["qwen2.5-7b-instruct-q4_k_m.gguf"], "llm_connected": True}):
            result = self.client.post("/intelligence/fixture/lanes/local/test")
        self.assertTrue(result.json()["passed"])
        self.assertIn("qwen2.5", result.json()["sample_output"])

    def test_unwired_response_test_does_not_fabricate_inference(self):
        with patch.object(intelligence.vault_client, "call") as call:
            result = self.client.post("/intelligence/fixture/lanes/local/test-response")
        self.assertEqual(result.status_code, 501)
        call.assert_not_called()
