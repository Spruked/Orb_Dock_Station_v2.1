"""Measured health only; no seeded pointer, provider, or recovery claims."""
import json
from urllib.request import urlopen
from fastapi import HTTPException
from app.models import HealthStatus

class HealthMonitor:
    def _status(self):
        try:
            with urlopen("http://127.0.0.1:16521/status", timeout=5) as response:
                return json.load(response)
        except Exception:
            return {}

    def get_overall_health(self):
        state = self._status()
        return {"pointer_confidence": 0, "model_reachability": "healthy" if state.get("llm_connected") else "unknown",
                "voice_reachability": "healthy" if state.get("tts_loaded") else "unknown",
                "overall": "degraded", "checks": {"governance_connected": False, "pointer_total": 0}}

    def get_pointer_report(self):
        return {"targets": [], "verified_count": 0, "needs_recovery": [], "deprecated_count": 0}

    def get_gateway_report(self):
        state = self._status()
        return {"lanes": [{"name": "local", "provider": "llama.cpp", "healthy": bool(state.get("llm_connected"))}],
                "active_lane": "local", "routing_status": "local_only"}

    def run_pointer_recovery(self):
        raise HTTPException(501, "Pointer runtime is not connected")

    def get_diagnostics(self):
        return []

health_monitor = HealthMonitor()
