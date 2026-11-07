"""Single-active-presentation registry owned by DockStation."""
from __future__ import annotations
from datetime import datetime, timezone
import time
from threading import RLock
from typing import Any

class DockingRegistry:
    def __init__(self) -> None:
        self._lock = RLock(); self._generation = 0; self._docks: dict[str, dict[str, Any]] = {}; self._active: str | None = None; self._pending: dict[str, Any] | None = None; self._pending_deadline = 0.0
    def _expire_pending(self) -> None:
        if self._pending and time.monotonic() >= self._pending_deadline:
            self._pending = None; self._pending_deadline = 0.0
    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        dock_id = payload["dock_id"]
        with self._lock:
            current = self._docks.get(dock_id); generation = current["dock_generation"] if current else self._generation + 1
            self._generation = max(self._generation, generation)
            record = {**payload, "dock_generation": generation, "lease_status": "active" if self._active == dock_id else "available", "health_status": "ready", "registered_at": datetime.now(timezone.utc).isoformat()}
            self._docks[dock_id] = record; return dict(record)
    def heartbeat(self, dock_id: str, health_status: str = "ready") -> dict[str, Any]:
        with self._lock:
            record = self._docks.get(dock_id)
            if not record: raise KeyError(dock_id)
            record["health_status"] = health_status; record["last_heartbeat"] = datetime.now(timezone.utc).isoformat(); return dict(record)
    def transfer(self, dock_id: str) -> dict[str, Any]:
        raise PermissionError("Direct transfer is disabled; use prepare then acknowledge")
    def prepare(self, dock_id: str, context: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._expire_pending()
            record = self._docks.get(dock_id)
            if not record or record.get("health_status") != "ready": raise KeyError(dock_id)
            self._generation += 1
            self._pending = {"dock_id": dock_id, "previous_dock_id": self._active, "dock_generation": self._generation, "context": context}
            self._pending_deadline = time.monotonic() + 30.0
            return dict(self._pending)
    def acknowledge(self, dock_id: str, generation: int) -> dict[str, Any]:
        with self._lock:
            self._expire_pending()
            pending = self._pending
            if not pending or pending["dock_id"] != dock_id or pending["dock_generation"] != generation: raise KeyError(dock_id)
            previous = self._active
            if previous and previous in self._docks: self._docks[previous]["lease_status"] = "available"
            self._active = dock_id; self._docks[dock_id]["lease_status"] = "active"; self._docks[dock_id]["dock_generation"] = generation; self._docks[dock_id]["previous_dock_id"] = previous; self._pending = None
            return {"active_dock_id": dock_id, "previous_dock_id": previous, "dock_generation": generation, "context": pending["context"], "dock": dict(self._docks[dock_id])}
    def rollback(self, dock_id: str, generation: int) -> dict[str, Any]:
        with self._lock:
            self._expire_pending()
            if not self._pending or self._pending["dock_id"] != dock_id or self._pending["dock_generation"] != generation: raise KeyError(dock_id)
            pending = self._pending; self._pending = None; return {"rolled_back": True, **pending}
    def recover(self) -> dict[str, Any]:
        with self._lock:
            active = self._docks.get(self._active) if self._active else None
            if active and active.get("health_status") == "ready": return {"recovered": False, "active_dock_id": self._active}
            if active and not active.get("fenced_generation") == active.get("dock_generation"):
                return {"recovered": False, "requires_fence": True, "active_dock_id": self._active, "dock_generation": active.get("dock_generation")}
            previous = active.get("previous_dock_id") if active else None
            if previous and previous in self._docks and self._docks[previous].get("health_status") == "ready":
                self._active = previous; self._docks[previous]["lease_status"] = "active"
                if active: active["lease_status"] = "available"
                return {"recovered": True, "active_dock_id": previous}
            self._active = None
            return {"recovered": False, "active_dock_id": None, "requires_dockstation": True}
    def fence(self, dock_id: str, generation: int) -> dict[str, Any]:
        with self._lock:
            record = self._docks.get(dock_id)
            if not record or record.get("dock_generation") != generation: raise KeyError(dock_id)
            record["fenced_generation"] = generation; record["lease_status"] = "fenced"
            return {"fenced": True, "dock_id": dock_id, "dock_generation": generation}
    def release(self, dock_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._docks.get(dock_id)
            if not record: raise KeyError(dock_id)
            if self._active == dock_id: self._active = None
            record["lease_status"] = "available"; return dict(record)
    def status(self) -> dict[str, Any]:
        with self._lock:
            self._expire_pending()
            return {"active_dock_id": self._active, "dock_generation": self._generation, "pending_transfer": dict(self._pending) if self._pending else None, "docks": [dict(item) for item in self._docks.values()]}

docking_registry = DockingRegistry()
