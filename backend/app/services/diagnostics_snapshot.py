"""Read-only measurements; missing producers never imply stopped or healthy."""
import json
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

STARTED = time.monotonic()
INSTANCE = str(uuid.uuid4())
STARTED_AT = datetime.now(timezone.utc).isoformat()


def metric(value=None, source="dock_backend", reason=None):
    stamp = datetime.now(timezone.utc).isoformat()
    return dict(value=value, status="unknown" if value is None else "measured",
                measured_at=stamp if value is not None else None, received_at=stamp,
                source=source, reason=reason)


AREAS = {
    "Hardware and resources": "gpu_memory_used gpu_memory_free gpu_utilization gpu_temperature gpu_models cpu_per_runtime ram_per_runtime",
    "Intelligence and models": "active_model provider local_or_remote response_latency tokens_per_second failed_calls timed_out_calls remote_enabled",
    "Speech and hearing": "microphone listening cochlear distortion confidence heard_count corrected_count confirmed_count clarification_count stop_word_armed stop_word_last_trigger stop_word_latency tts_model tts_voice tts_generation_time voice_latency",
    "Memory AIMS": "session_id stm_size promotions collection_totals integrity_check writer_lock_owner failed_writes rejected_writes skg_nodes skg_links skg_last_update index_rebuild",
    "Cognition and governance": "ral_state active_goal proposals core4_results admission_decisions field_readings field_seed world_state_version world_state_age",
    "Authority and permits": "grants issued active expired revoked consumed rejected revocations",
    "Execution and Motion": "enabled disabled_reason queue_depth active_actions cancelled_actions cancellation_latency emergency_stop_armed emergency_stop_last_test watchdog",
    "Correspondence and verification": "awaiting_verification verified contradicted unknown partial discrepancies",
    "Orb and dock state": "docked visible position behavior skin settings_applied_live",
    "Security": "route_authentication rejected_requests failed_logins doctrine_hash policy_hash",
    "Activity log": "correlated_events",
}


def poll(pair):
    name, port = pair
    try:
        with urlopen(f"http://127.0.0.1:{port}/diagnostics", timeout=1) as response:
            data = json.load(response)
        if data.get("runtime") != name or data.get("schema_version") != 1:
            raise ValueError("Unsupported telemetry producer")
        return name, data["metrics"]
    except (OSError, ValueError, KeyError):
        return name, {"running": metric(source=name, reason="No current producer measurement; process state unknown")}


def snapshot():
    with ThreadPoolExecutor(max_workers=3) as pool:
        runtimes = dict(pool.map(poll, [("communication", 16521), ("cognition_governance", 16524), ("motion", 16525)]))
    runtimes["dock_backend"] = {key: metric(value) for key, value in {
        "running": True, "pid": os.getpid(), "uptime_seconds": time.monotonic() - STARTED,
        "instance_started_at": STARTED_AT, "process_instance_id": INSTANCE}.items()}
    for name in ("vault_aims", "llama_cpp"):
        prefix = name + "."
        runtimes[name] = {key.removeprefix(prefix): value for key,value in runtimes["communication"].items() if key.startswith(prefix)} or {
            "running": metric(source=name, reason="Communication measurement unavailable")}
    sections = {name: {key: metric(reason="Measurement not connected") for key in keys.split()}
                for name, keys in AREAS.items()}
    sections["Runtime health"] = {f"{name}.{key}": value for name, values in runtimes.items() for key, value in values.items()}
    sections["Professional foundation"] = {
        key.removeprefix("inculcation."): value
        for key, value in runtimes["communication"].items() if key.startswith("inculcation.")
    } or {"validated": metric(reason="Communication foundation producer unavailable")}
    for key,value in runtimes["communication"].items():
        if key.startswith("voice."):
            sections["Speech and hearing"][key.removeprefix("voice.")] = value
        if key.startswith("vault_aims."):
            sections["Memory AIMS"][key.removeprefix("vault_aims.")] = value
    for name in ("enabled", "disabled_reason"):
        sections["Execution and Motion"][name] = runtimes["motion"].get(name, metric(reason="Motion producer unavailable"))
    cognition = runtimes["cognition_governance"]
    for key, value in cognition.items():
        if key.startswith("field."):
            sections["Cognition and governance"][key] = value
    root = Path(__file__).resolve().parents[4] / "Orbot"
    for name, path in {"vault": root / "Orbot_Vault-Logic-System/.local/host_memory",
                       "aims": root / "Orbot_Vault-Logic-System/AIMS",
                       "models": root / ".local/models"}.items():
        if path.exists():
            try:
                usage = shutil.disk_usage(path)
                for key in ("free", "total"):
                    sections["Hardware and resources"][f"disk_{name}_{key}_bytes"] = metric(getattr(usage, key), "dock_os")
            except OSError:
                pass
    return {"schema_version": 1, "collected_at": datetime.now(timezone.utc).isoformat(),
            "stale_after_seconds": 15, "sections": sections}
