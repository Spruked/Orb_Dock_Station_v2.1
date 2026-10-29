# Dock companion integration for Orbot's professional foundation

This records the original status-only integration. The subsequent Dock-owned
startup phase is implemented separately in this repository; see
`dock_owned_startup_implementation.md` and the native acceptance JSON reports.

Date: October 28, 2026.

Owning repository: `Spruked/Orb_Dock_Station_v2.1`, verified origin
`https://github.com/Spruked/Orb_Dock_Station_v2.1.git`, branch `main`.
This is independent of `Spruked/Orbot`. The working tree already contained
extensive modified/deleted/untracked files before this task. Those changes are
not attributed to the inculcation integration. No commit or push was made.

## Changes attributable to the inculcation task

- `backend/app/routers/diagnostics.py`: added authenticated
  `GET /diagnostics/inculcation` forwarding through the existing server-side
  VaultClient to Communication's `GET /inculcation/status`.
- `backend/app/services/diagnostics_snapshot.py`: added the Professional
  foundation section from Communication's existing `inculcation.*` telemetry.
  This file was already untracked; the task added that section, not the whole
  diagnostics implementation.
- `backend/tests/test_inculcation_status.py`: added three API tests.

The existing Diagnostics screen renders the new telemetry section dynamically;
no frontend changes were made for this integration. The authenticated route
passes no write payload. Dock adds no education-update endpoint, private
foundation store, AIMS writer, authority issuer or model-service control.

## Owning verification

From this repository's `backend` directory:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests
```

Three tests passed: anonymous requests cannot read status, authenticated requests
use the existing client without a write payload, and POST updates are unavailable.
These are Dock tests, not part of Orbot's 98-test verification count.

## Dependency and limitations

The owner's corrected target makes Dock the primary launch/activation environment,
with Orbot initially docked and the same active session across dock/release
transitions. The status integration below does not implement or verify that
launch chain. Orbot's `docs/dock_startup_lifecycle_verification.md` records the
source trace and the remaining Dock-owned and Orbot-owned changes.

The active inculcation and loader belong to `Spruked/Orbot`. This companion
integration depends on its existing Communication service at loopback `16521`
and the existing server-side Vault token interface. It is not required for
Orbot's foundation to load. Missing Communication produces the client's existing
unavailable response; there is no local authoritative fallback.

Existing development authentication limitations remain as recorded in the
baseline assessment. This status integration neither resolves them nor grants
broader access. VIV and Prime Mail integration belongs to their respective
authenticated application interfaces and remains separate work.
