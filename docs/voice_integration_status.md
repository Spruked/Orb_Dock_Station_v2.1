# Dock voice integration

Dock owns the new live voice status and microphone controls in `frontend/src/components/VoiceStatus.jsx`, native commands in `desktop/src-tauri/src/desktop_host.rs`, Docking Bay integration, and synthesis-test timeout in `backend/app/services/vault_client.py`. Microphone preferences are written only through Orbot's existing HostMemory/AIMS gateway. Voice remains active while docked unless explicitly paused.

The owner-confirmed input is Desktop Microphone (Realtek(R) Audio). Three actual launch/recall cycles preserved the same session, microphone stream, runtimes and foundation activation. See `voice_docking_continuity_results.json`, `voice_device_acceptance_results.json` and `voice_final_deployment.json`. Tauri playback reached an end event, and the owner subsequently confirmed: "Yes, I heard the reply."

Dock backend: 14 tests passed. Frontend and native custom-protocol builds passed. Full cross-repository implementation report: `../Orbot/docs/voice_runtime_integration_report.md` relative to the Dock repository root. Each repository retains its own ownership and working tree. No commits or dependency installs were made.
