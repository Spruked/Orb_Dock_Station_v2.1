"""Dock-owned persistent voice library. It never reads the source application."""
from __future__ import annotations

import json
import shutil
import uuid
import wave
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings


class VoiceLibrary:
    def __init__(self):
        self.root = Path(settings.VOICE_LIBRARY_DIR).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.root / "catalog.json"
        if not self.catalog_path.exists():
            self._write({"schema": 1, "voices": []})

    def _read(self):
        try:
            value = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            return value if isinstance(value.get("voices"), list) else {"schema": 1, "voices": []}
        except (OSError, ValueError):
            raise HTTPException(503, "Voice library catalog is unavailable or invalid")

    def _write(self, value):
        temp = self.catalog_path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp.replace(self.catalog_path)

    def list(self):
        return self._read()["voices"]

    def get(self, voice_id):
        return next((v for v in self.list() if v.get("id") == voice_id), None)

    def path(self, relative):
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents:
            raise HTTPException(400, "Voice asset path escapes the library")
        return candidate

    def preview_path(self, voice_id):
        voice = self.get(voice_id)
        if not voice or not voice.get("preview"): raise HTTPException(404, "Voice preview not found")
        path = self.path(voice["preview"])
        if not path.is_file(): raise HTTPException(404, "Voice preview asset is missing")
        return path

    async def import_sample(self, upload: UploadFile, name: str):
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix != ".wav": raise HTTPException(400, "Only WAV voice samples are supported")
        voice_id = "custom-" + uuid.uuid4().hex[:12]
        relative = f"samples/{voice_id}.wav"
        destination = self.root / relative
        data = await upload.read()
        if len(data) > 50 * 1024 * 1024: raise HTTPException(413, "Voice sample exceeds 50 MiB")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        try:
            with wave.open(str(destination), "rb") as audio:
                duration = audio.getnframes() / max(audio.getframerate(), 1)
                if audio.getnchannels() < 1 or duration < 1 or duration > 120:
                    raise ValueError
        except (wave.Error, OSError, ValueError):
            destination.unlink(missing_ok=True)
            raise HTTPException(400, "Voice sample is not a valid 1–120 second WAV file")
        catalog = self._read()
        entry = {"id": voice_id, "name": name.strip()[:80] or voice_id,
                 "sample": relative, "preview": relative, "profile_id": None,
                 "status": "preview_only", "source": "dock_import"}
        catalog["voices"].append(entry); self._write(catalog)
        return entry


voice_library = VoiceLibrary()
