"""Dock data goes to AIMS via Orbot's local gateway; never a private data store."""
import json
import os
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from fastapi import HTTPException


class VaultClient:
    def __init__(self):
        workspace = Path(__file__).resolve().parents[4]
        default = workspace / "Orbot/Orbot_Vault-Logic-System/.local/host-memory.token"
        self.token_path = Path(os.getenv("ORBOT_VAULT_TOKEN_FILE", str(default)))
        self.endpoint = "http://127.0.0.1:16521"
        self.revisions = threading.local()

    def call(self, route, payload=None):
        try:
            token = self.token_path.read_text(encoding="utf-8").strip()
            request = Request(self.endpoint + route,
                data=None if payload is None else json.dumps(payload, default=str).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            with urlopen(request, timeout=300 if route == "/voice/synthesize" else 15) as response:
                return json.load(response)
        except Exception:
            raise HTTPException(503, "Qwen3-TTS synthesis failed or timed out; check voice diagnostics" if route.startswith("/voice/") else "AIMS Vault unavailable or write conflicted; no local fallback was used")

    def read(self, name, default=None):
        result = self.call("/memory/collections/" + name)
        if not hasattr(self.revisions, "values"):
            self.revisions.values = {}
        self.revisions.values[name] = result.get("entry_id")
        return result["value"] if result["value"] is not None else default

    def write(self, name, value, reason):
        if not hasattr(self.revisions, "values"):
            self.revisions.values = {}
        revisions = getattr(self.revisions, "values", {})
        result = self.call("/memory/collections/" + name,
                          {"payload": value, "reason": reason, "expected_entry_id": revisions.get(name)})
        self.revisions.values[name] = result["entry_id"]
        return result


vault_client = VaultClient()
