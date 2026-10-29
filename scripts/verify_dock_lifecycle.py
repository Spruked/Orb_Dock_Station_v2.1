"""Real native startup/release/recall verification, with temporary AIMS data.

Requires free application ports and an already running shared llama.cpp service.
Never stops or replaces pre-existing services. Run after both native builds.
"""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError

DOCK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOCK / "backend"))
from desktop_lifecycle import request, occupied


class AcceptanceFailure(RuntimeError):
    pass


def wait(check, seconds=180):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except AcceptanceFailure:
            raise
        except Exception as error:
            last = str(error)
        time.sleep(0.2)
    raise RuntimeError("Native acceptance wait failed: " + str(last))


def model_pid():
    output = subprocess.check_output(["powershell", "-NoProfile", "-Command",
        "(Get-NetTCPConnection -LocalPort 16520 -State Listen).OwningProcess | Select-Object -Unique"], text=True)
    return output.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attach-communication", action="store_true", help="Verify connection to a separately owned runtime fixture")
    args = parser.parse_args()
    ports = (8000, 16521, 16522, 16523, 16524, 16525)
    if any(occupied(port) for port in ports):
        raise RuntimeError("Application ports must be free; existing processes were preserved")
    model_before = model_pid()
    report = {"shared_model_pid_before": model_before, "transitions": [], "passed": False,
              "measured_at": datetime.now(timezone.utc).isoformat(),
              "production_memory_touched": False}
    orb_exe = DOCK.parent / "Orbot/desktop/src-tauri/target/debug/orbot-desktop.exe"
    dock_exe = DOCK / "desktop/src-tauri/target/debug/orbot-dock-station.exe"
    env = dict(os.environ)
    env.pop("ORBOT_DOCK_LAUNCH", None)
    direct = subprocess.run([str(orb_exe)], env=env, timeout=10)
    if direct.returncode != 0 or occupied(16523):
        raise RuntimeError("Direct independent Orbot launch was not cleanly refused")
    report["direct_launch_refused"] = True
    with tempfile.TemporaryDirectory(prefix="orbot-native-lifecycle-") as directory:
        temporary = Path(directory).resolve()
        env.update(ORBOT_HOST_MEMORY_ROOT=str(temporary / "host_memory"),
                   ORBOT_VAULT_TOKEN_FILE=str(temporary / "host-memory.token"), ORBOT_DOCK_ROOT=str(DOCK))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        fixture = None
        fixture_instance = None
        if args.attach_communication:
            python = DOCK.parent / "Orbot/runtime/communication/.venv/Scripts/python.exe"
            fixture = subprocess.Popen([str(python), "-B", "-m", "runtime.communication.main"],
                env=env, cwd=DOCK.parent / "Orbot", creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fixture_instance = wait(lambda: request(16521, "/health") if request(16521, "/health").get("ready") else None)["process_instance_id"]
            report["attached_fixture_instance"] = fixture_instance
        dock = subprocess.Popen([str(dock_exe)], env=env, cwd=DOCK, creationflags=flags)
        launch = None
        token = None
        try:
            launch = wait(lambda: request(16522, "/status"), seconds=30)["launch_id"]
            def ready():
                status = request(16522, "/status")
                if status["lifecycle"].get("phase") == "failed":
                    raise AcceptanceFailure(status["lifecycle"].get("error"))
                return status if status["lifecycle"].get("ready") else None
            status = wait(ready)
            launch = status["launch_id"]
            token = (temporary / "host-memory.token").read_text().strip()
            initial = request(16523, "/status", launch_id=launch)
            assert initial["docked"] is True and initial["visible"] is False and initial["renderer_ready"] is True
            report["initial"] = initial
            report["startup"] = status["lifecycle"]
            assert status["lifecycle"]["services"]["communication"]["owned"] is not args.attach_communication
            if fixture_instance:
                assert status["lifecycle"]["communication_instance"] == fixture_instance
            identities = {name: request(port, "/diagnostics")["process_instance_id"]
                          for name, port in (("communication",16521),("cognition_governance",16524),("motion",16525))}
            report["runtime_instances"] = identities
            try:
                request(16522, "/release", {}, launch_id=launch, token="invalid-fixture")
                raise AcceptanceFailure("Unauthenticated native lifecycle mutation was accepted")
            except HTTPError as error:
                assert error.code == 401
                report["invalid_credential_rejected"] = True
            session = request(16521, "/sessions/embodiment", {}, token=token)["session_id"]
            report["session_identity_sha256"] = hashlib.sha256(session.encode()).hexdigest()
            foundation = request(16521, "/inculcation/status", token=token)
            # A simultaneous runtime launch must fail before opening any writer.
            competing_root = temporary / "must-not-be-created"
            competing_env = dict(env, ORBOT_HOST_MEMORY_ROOT=str(competing_root))
            competing = subprocess.run([str(DOCK.parent / "Orbot/runtime/communication/.venv/Scripts/python.exe"),
                "-B", "-m", "runtime.communication.main"], env=competing_env, cwd=DOCK.parent / "Orbot",
                capture_output=True, timeout=15, creationflags=flags)
            assert competing.returncode != 0 and not competing_root.exists()
            report["competing_writer_refused_before_memory_open"] = True
            request(16521, "/conversation", {"session_id": session, "text": "Our goal is to plan Blue Lantern. Acknowledge briefly.",
                                               "objective": "Plan Blue Lantern", "speak": False})
            for index in range(3):
                request(16522, "/release", {}, launch_id=launch, token=token)
                released = request(16523, "/status", launch_id=launch)
                assert released["visible"] is True and released["docked"] is False
                request(16522, "/dock", {}, launch_id=launch, token=token)
                recalled = request(16523, "/status", launch_id=launch)
                assert recalled["visible"] is False and recalled["docked"] is True
                same_session = request(16521, "/sessions/embodiment", {}, token=token)["session_id"]
                same_foundation = request(16521, "/inculcation/status", token=token)
                now = request(16522, "/status")["lifecycle"]
                assert same_session == session
                assert same_foundation["sha256"] == foundation["sha256"]
                assert same_foundation["activation_entry_id"] == foundation["activation_entry_id"]
                assert now["communication_instance"] == status["lifecycle"]["communication_instance"]
                assert now["orb_pid"] == status["lifecycle"]["orb_pid"]
                for name, port in (("communication",16521),("cognition_governance",16524),("motion",16525)):
                    assert request(port, "/diagnostics")["process_instance_id"] == identities[name]
                report["transitions"].append({"cycle": index + 1, "released": released, "recalled": recalled,
                    "same_session": True, "same_foundation_activation": True, "same_processes": True})
            reply = request(16521, "/conversation", {"session_id": session, "text": "What is our objective? Repeat it briefly.", "speak": False})
            report["continuity_response"] = reply["text"]
            assert "blue lantern" in reply["text"].lower()
            report["foundation"] = foundation["sha256"]
            report["activation_entry_id"] = foundation["activation_entry_id"]
            request(16522, "/shutdown", {}, launch_id=launch, token=token)
            dock.wait(timeout=15)
            owned_ports = tuple(port for port in ports if not (args.attach_communication and port == 16521))
            wait(lambda: not any(occupied(port) for port in owned_ports), seconds=40)
            report["owned_ports_closed"] = True
            if fixture:
                assert request(16521, "/health")["process_instance_id"] == fixture_instance
                assert request(16521, "/sessions/embodiment", token=token)["session_id"] is None
                report["attached_runtime_preserved"] = True
                request(16521, "/lifecycle/shutdown", {"process_instance_id": fixture_instance}, token=token)
                fixture.wait(timeout=20)
                wait(lambda: not occupied(16521), seconds=10)
            report["shared_model_pid_after"] = model_pid()
            assert model_before == report["shared_model_pid_after"]
            report["passed"] = True
        finally:
            if dock.poll() is None and launch:
                try:
                    request(16522, "/shutdown", {}, launch_id=launch, token=token)
                    dock.wait(timeout=15)
                except Exception:
                    dock.terminate()
                    dock.wait(timeout=10)
            if fixture is not None and fixture.poll() is None:
                try:
                    request(16521, "/lifecycle/shutdown", {"process_instance_id": fixture_instance}, token=token)
                    fixture.wait(timeout=20)
                except Exception:
                    fixture.terminate()
                    fixture.wait(timeout=10)
            # Leave a failed native application available for diagnosis rather
            # than force-killing unrelated or unverified processes.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
