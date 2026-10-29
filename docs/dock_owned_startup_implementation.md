> Updated voice requirement: docking preserves communication, microphone capture and playback. Pause/Cancel are explicit owner controls. Microphone input is selectable in the Docking Bay and saved through the existing AIMS writer.

# Dock-owned startup implementation

Date: October 28, 2026. Owner: `Spruked/Orb_Dock_Station_v2.1`.
The initial docked state is mandatory. This report supersedes earlier descriptions
of Dock as an optional companion waiting for an independently started Orb.

## Changes in this repository

- `desktop/src-tauri/src/desktop_host.rs`: starts one lifecycle coordinator for
  the running Dock instance; provides startup status/retry, guarded release,
  recall, Show and Quit; rejects stale launch identity and missing existing
  Vault credentials on lifecycle mutations. A coordinator that exits cannot
  leave a stale ready indication. The native HTTP handlers are concurrent so
  release readiness callbacks cannot deadlock Dock.
- `backend/desktop_lifecycle.py`: initializes the management API first, starts
  missing Orbot runtimes or validates existing services, verifies professional
  foundation agreement, creates/reuses the runtime embodiment session, and
  launches the built Orb hidden/docked. It monitors required runtime readiness
  and the Communication instance rather than trusting occupied ports.
- `frontend/src/panels/DockingBay.jsx`: displays startup phase/errors and enables
  Release only when initialization is ready. Recall uses the same native host.
- Cargo declares `custom-protocol` for self-contained native builds and uses
  the existing reqwest JSON support. No model/dependency installer is added.
- `backend/tests/test_desktop_lifecycle.py`: validates service identity, readiness,
  unknown-port preservation, attachment without spawn, shutdown ownership and
  preservation of Communication if durable review cannot be confirmed.
- `scripts/verify_dock_lifecycle.py`: real built-application verification with
  temporary AIMS data, normal and pre-existing-Communication modes.

State/logs are local ignored runtime files under `.local/lifecycle-<id>.*`.
The existing Vault credential remains server-side. No private Dock vault or
second authoritative memory writer is introduced. A launch ID correlates the
Dock/Orb lifecycle; it is not a capability grant or an execution permit.

## Ownership and shutdown

Only processes created by this coordinator are stopped as owned children.
Existing ready runtimes and an existing management backend are attached and
preserved. The embodiment session is explicitly reconciled at application Quit.
An owned Communication runtime receives its authenticated, instance-bound
graceful-shutdown request; failed persistence/review leaves it alive for recovery.
Shared llama.cpp is connected to and is never restarted or stopped by Dock.

Orbot's repository owns the hidden/docked initial presentation, guarded native
release, voice suspension versus session completion, runtime-owned session and
education v1.3. See its `docs/dock_owned_lifecycle_implementation.md`.

## Reproduce

Build Orbot first using its own documented commands, then from this repository:

```powershell
npm --prefix frontend run build
& "$env:USERPROFILE/.cargo/bin/cargo.exe" build --features custom-protocol --manifest-path desktop/src-tauri/Cargo.toml
& .\desktop\src-tauri\target\debug\orbot-dock-station.exe
```

The source checkout and existing Python environments must remain available.
The default Orb executable is the sibling Orbot build at
`desktop/src-tauri/target/debug/orbot-desktop.exe`; an explicit owner deployment
can set `ORBOT_EXECUTABLE`. Existing Vite servers are unnecessary for the embedded
builds. Missing prerequisites produce an explicit startup error and retry option.

Run repository tests from `backend`:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests
```

Eleven tests pass: eight lifecycle tests plus the existing three foundation-status
API tests. Native build succeeds. The frontend build succeeds with its existing
large-chunk advisory. Optional rustfmt is not installed; no formatter toolchain
was installed by this task.

Run actual native verification from the Dock repository with application ports
free and the shared model already running:

```powershell
backend/.venv/Scripts/python.exe -B scripts/verify_dock_lifecycle.py --output docs/dock_lifecycle_acceptance_results.json
backend/.venv/Scripts/python.exe -B scripts/verify_dock_lifecycle.py --attach-communication --output docs/dock_lifecycle_attach_results.json
```

The harness refuses to stop or replace existing application-port owners. It
injects temporary AIMS/token paths only into its own test processes. Production
memory is untouched. Reports hash the session ID instead of publishing it.

The acceptance criteria are: direct standalone Orb launch refused; initial Orb
`docked=true`, `visible=false`, renderer ready; invalid credentials rejected;
competing Communication launch refused before opening a writer; three release/
recall cycles retain the same session, foundation activation and runtime
instances; objective continuity; owned resources close on Quit; shared model PID
unchanged. The attachment scenario additionally requires that the separately
owned Communication fixture survives Dock Quit with its instance unchanged.

Both native reports passed. Each verifies three release/recall cycles, unchanged
session/foundation/runtime identities, objective recall, rejection of invalid
credentials, competing-writer refusal before memory initialization, and owned
resource shutdown. The attachment report additionally confirms that Dock preserved
the separately owned Communication instance and ended only the embodiment session.
The shared llama.cpp PID remained `11804` in both recorded runs. Production AIMS
data was not touched; test applications and fixtures were shut down afterward.

The JSON reports contain actual outcomes. This phase does not enable autonomous
tools, Motion execution, new permits, VIV/Mail adapters, or sealed Doctrine
validation. Existing Dock login-hardening work remains separate. No commits or
pushes were made; pre-existing repository edits were preserved.
