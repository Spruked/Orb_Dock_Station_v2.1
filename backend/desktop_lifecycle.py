"""Dock-owned application lifecycle; never owns the shared model service.

Launch identity correlates native presentation with its Dock instance. It is not
an execution permit. Memory calls use the existing server-side Vault credential.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import Request, urlopen

RUNTIMES = {"communication": 16521, "cognition_governance": 16524, "motion": 16525}


def request(port, path, payload=None, launch_id=None, token=None):
    headers = {"Content-Type": "application/json", "X-Orbot-Desktop": "1"}
    if launch_id:
        headers["X-Orbot-Launch"] = launch_id
    if token is None and payload is not None and port in (16522, 16523):
        path_default = Path(__file__).resolve().parents[2] / "Orbot/Orbot_Vault-Logic-System/.local/host-memory.token"
        token = Path(os.getenv("ORBOT_VAULT_TOKEN_FILE", str(path_default))).read_text(encoding="utf-8").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(f"http://127.0.0.1:{port}{path}",
                  data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    with urlopen(req, timeout=3) as response:
        return json.load(response)


def occupied(port):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def validate_runtime(name, health):
    if health.get("runtime") != name:
        raise RuntimeError(f"Port {RUNTIMES[name]} is not the expected {name} runtime; preserving it")
    if health.get("execution_authority") is not False:
        raise RuntimeError(f"Unexpected execution mode on {name}; not attaching")
    return health.get("ready") is True


class Lifecycle:
    def __init__(self, dock_root, launch_id, report):
        self.dock = Path(dock_root).resolve()
        self.orbot = self.dock.parent / "Orbot"
        self.launch_id = launch_id
        self.report = Path(report)
        self.children = []
        self.communication_instance = None
        self.native = None
        self.state = {"launch_id": launch_id, "phase": "starting", "ready": False, "services": {}}
        self.log = None

    def update(self, phase, **fields):
        self.state.update(phase=phase, **fields)
        self.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state), encoding="utf-8")
        temporary.replace(self.report)

    def dock_alive(self):
        try:
            status = request(16522, "/status")
            return status.get("application") == "station" and status.get("launch_id") == self.launch_id
        except Exception:
            return False

    def spawn(self, name, args, cwd, env=None):
        if not self.dock_alive():
            raise RuntimeError("Owning Dock instance ended before startup completed")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        child = subprocess.Popen(args, cwd=cwd, env=env, stdout=self.log, stderr=self.log,
                                 creationflags=flags)
        self.children.append((name, child))
        return child

    def wait(self, check, child=None, seconds=180):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self.dock_alive():
                raise RuntimeError("Owning Dock instance ended during startup")
            if child is not None and child.poll() is not None:
                raise RuntimeError(f"Owned startup process exited with code {child.returncode}; see lifecycle log")
            try:
                result = check()
                if result:
                    return result
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        raise RuntimeError("Required component did not become ready within 180 seconds")

    def runtime(self, name):
        port = RUNTIMES[name]
        child = None
        if occupied(port):
            try:
                validate_runtime(name, request(port, "/health"))
            except Exception as error:
                raise RuntimeError(f"Cannot identify existing {name} service; preserving port {port}") from error
        else:
            python = self.orbot / "runtime/communication/.venv/Scripts/python.exe"
            if not python.is_file():
                raise RuntimeError("Existing Orbot runtime Python is missing; no installation attempted")
            child = self.spawn(name, [str(python), "-B", "-m", f"runtime.{name}.main"], self.orbot)
        def ready():
            health = request(port, "/health")
            return health if validate_runtime(name, health) else None
        health = self.wait(ready, child)
        self.state["services"][name] = {"owned": child is not None, "port": port,
                                         "pid": child.pid if child else None}
        if name == "communication":
            self.communication_instance = health.get("process_instance_id")
            if not self.communication_instance or not health.get("professional_foundation", {}).get("validated"):
                raise RuntimeError("Communication lacks validated professional-foundation readiness")
            self.state["foundation_sha256"] = health["professional_foundation"]["sha256"]
            self.state["communication_instance"] = self.communication_instance
        if name == "cognition_governance" and health.get("professional_foundation", {}).get("sha256") != self.state["foundation_sha256"]:
            raise RuntimeError("Cognition and Communication disagree about professional foundation")

    def start(self):
        self.log = open(self.report.with_suffix(".log"), "ab", buffering=0)
        # Initialize management first, without creating a second memory writer.
        self.update("management")
        def backend_ready():
            health = request(8000, "/health")
            if health.get("app") != "ORB Dock Station Authority":
                raise RuntimeError("Port 8000 belongs to an unexpected application")
            return health.get("status") == "ok"
        child = None
        if occupied(8000):
            backend_ready()
        else:
            python = self.dock / "backend/.venv/Scripts/python.exe"
            if not python.is_file():
                raise RuntimeError("Existing Dock backend Python is missing; no installation attempted")
            child = self.spawn("management", [str(python), "-B", "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", "8000"], self.dock / "backend")
        self.wait(backend_ready, child)
        for name in RUNTIMES:
            self.update("initializing_" + name)
            self.runtime(name)
        token = self.token()
        request(16521, "/sessions/embodiment", {}, token=token)
        self.update("launching_docked_embodiment")
        if occupied(16523):
            raise RuntimeError("An existing native Orb owns port 16523; it was not replaced or adopted")
        executable = Path(os.environ.get("ORBOT_EXECUTABLE") or self.orbot /
                          "desktop/src-tauri/target/debug/orbot-desktop.exe")
        if not executable.is_file():
            raise RuntimeError("Built Orbot executable is missing; build Orbot before starting Dock")
        env = dict(os.environ, ORBOT_DOCK_LAUNCH=self.launch_id, ORBOT_REPO_ROOT=str(self.orbot))
        self.native = self.spawn("embodiment", [str(executable)], self.orbot, env)
        def native_ready():
            status = request(16523, "/status", launch_id=self.launch_id)
            if status.get("application") != "orb" or status.get("launch_id") != self.launch_id:
                raise RuntimeError("Native Orb identity does not match its owning Dock")
            if status.get("docked") is not True:
                raise RuntimeError("Initial docked-state invariant violated")
            if status.get("visible") is not False:
                raise RuntimeError("Initial Orb window must be hidden")
            if status.get("renderer_ready") is not True:
                return None
            return status
        self.wait(native_ready, self.native, seconds=30)
        self.update("ready", ready=True, orb_pid=self.native.pid)

    def token(self):
        path = Path(os.getenv("ORBOT_VAULT_TOKEN_FILE", str(self.orbot / "Orbot_Vault-Logic-System/.local/host-memory.token")))
        return path.read_text(encoding="utf-8").strip()

    def stop(self):
        # Never stop attached processes or the independently shared llama.cpp.
        self.update("stopping", ready=False)
        if self.native is not None and self.native.poll() is None:
            try:
                request(16523, "/shutdown", {}, launch_id=self.launch_id)
                self.native.wait(timeout=10)
            except Exception:
                pass
        try:
            health = request(16521, "/health")
            if self.communication_instance and health.get("process_instance_id") == self.communication_instance:
                active = request(16521, "/sessions/embodiment", token=self.token()).get("session_id")
                if active:
                    request(16521, "/sessions/end", {"session_id": active}, token=self.token())
        except Exception:
            self.state["cleanup_warning"] = "Embodiment session close not confirmed; retained runtime may require reconciliation"
        for name, child in reversed(self.children):
            if child.poll() is not None:
                continue
            if name == "communication":
                try:
                    request(16521, "/lifecycle/shutdown", {"process_instance_id": self.communication_instance}, token=self.token())
                    child.wait(timeout=15)
                except Exception as error:
                    # Pending memory is more valuable than forcing process exit.
                    self.state["cleanup_warning"] = "Communication preserved: durable session review/shutdown not confirmed"
                    continue
            else:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
        self.update("stopped", ready=False)
        if self.log:
            self.log.close()

    def run(self):
        error = None
        try:
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.start()
            while self.dock_alive():
                if any(child.poll() is not None for _, child in self.children):
                    raise RuntimeError("An owned application component exited; release is disabled")
                for name, port in RUNTIMES.items():
                    health = request(port, "/health")
                    if not validate_runtime(name, health):
                        raise RuntimeError(f"Required {name} runtime lost readiness")
                    if name == "communication" and health.get("process_instance_id") != self.communication_instance:
                        raise RuntimeError("Communication instance changed; automatic session rebinding refused")
                time.sleep(2.0)
        except Exception as caught:
            error = str(caught)
        finally:
            self.stop()
            if error:
                self.update("failed", ready=False, error=error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-id", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    Lifecycle(Path(__file__).resolve().parents[1], args.launch_id, args.report).run()
