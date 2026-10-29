# Orbot Dock Station (Tauri)

**Corrected intended lifecycle:** Dock Station is Orbot's primary launch and
activation environment. Orbot launches through Dock, starts docked, and is
released into its floating presentation with the same cognition and active
session. This lifecycle is now wired. See `docs/dock_owned_startup_implementation.md`
for build/start commands, ownership and native verification. Dock remains an
independent repository and does not become a vault writer.

This station is a separate project outside the Orbot Git repository. It retains
its existing React interface and runs in its own Tauri 2 / Rust desktop host.
Electron and Docker entrypoints have been removed.

The main window opens on the docking bay. Closing it hides it to the system
tray; the tray can restore it, release/recall Orbot, or quit. Dock starts or
connects the required runtimes and launches Orbot docked. Docking hides its floating window and shows its supplied
red/blue image in the bay. Undocking restores the same process.

## Build

Rust/Cargo, MSVC C++ tools, and WebView2 are required on Windows. On this machine
Cargo is under `%USERPROFILE%/.cargo/bin`; add it to your current terminal PATH.

```powershell
npm --prefix frontend ci
npm --prefix desktop ci
cd desktop
npm run dev
npm run build -- --debug --no-bundle
```

The frontend dev port is 1421; production assets are built into the native app.
The station control listener is loopback 16522; Orbot's is 16523. These control
only presentation and do not grant action authority.

## AIMS data and sessions

Start Orbot Communication on 16521 before authenticated configuration operations.
The backend reads its server-side token from
`../Orbot/Orbot_Vault-Logic-System/.local/host-memory.token`, overridable with
`ORBOT_VAULT_TOKEN_FILE`. Never copy that token into the frontend.

Profiles, versions, and skin uploads now go through the AIMS Vault adapter.
There are no private authoritative JSON, skin, or SQLite stores in this station.
Ordinary captured responses stay in isolated AIMS short-term session memory;
explicitly retained information and configuration go to long-term memory.
AIMS owns the immutable ledger and rebuildable SQLite projection inside Orbot.
Legacy files are not silently imported. Simulated conversations/statistics are
not seeded, and simulated execution endpoints are not mounted.

The imported owner login is still a development authentication implementation.
Keep the backend on loopback and harden credentials before wider deployment.
Start it with `backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir
backend --host 127.0.0.1 --port 8000`. The local environment was verified with
bcrypt 3.2.2 for passlib compatibility.

The `.git` directory removal was blocked by automatic approval policy. It remains
outside the Orbot repository. No changes were pushed for this project.
