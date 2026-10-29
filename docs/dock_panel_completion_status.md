> Updated voice requirement: docking preserves communication, microphone capture and playback. Pause/Cancel are explicit owner controls. Microphone input is selectable in the Docking Bay and saved through the existing AIMS writer.

# Dock panel integration status

This pass stays within the Dock repository.

Implemented: measured model connection checks through existing authenticated Communication /status; saved provider/model compared with running model; no fabricated timing, first-token timing, or generated response. Unwired response tests return 501. Frontend handles failed test requests. Saved lane selection is labeled as profile configuration rather than a running service switch.

The disabled legacy Live Test simulation has been replaced with an explicit integration status. Tools shows missing-profile, loading, empty, and error states and does not claim runtime authorization. Visible Behavior wording and new greeting defaults use Orbot. Existing owner-stored greetings are preserved. Speech synthesis failures are displayed.

Validation: 14 backend tests pass, including model mismatch and unwired response checks; Vite build passes with the existing bundle-size advisory.

Remaining work: connect profile application and acknowledgment to existing runtime interfaces; implement governed draft conversation testing; integrate actual runtime capability inventory and canonical permit checks; connect appearance previews to embodiment; verify conversation/statistics retention and visibility with real sessions. These require actual contracts and must not be represented as implemented by changing labels. Existing model runtime and Qwen3-TTS remain unchanged.
