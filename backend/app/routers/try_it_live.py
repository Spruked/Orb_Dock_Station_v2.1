"""Try It Live workflow — preview, test, publish, restore"""
from fastapi import APIRouter, HTTPException, Depends, Header
from app.models import TryItLiveResult, ProfileState
from app.services.profile_service import profile_service
from app.core.security import decode_token

router = APIRouter(prefix="/try-it-live", tags=["Try It Live"])

def _real_integration_required():
    raise HTTPException(
        status_code=503,
        detail="Try It Live is unavailable until it is connected to the real Orbot runtime services.",
    )

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/{profile_id}/preview")
async def preview_profile(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "profile_id": p.id,
        "name": p.name,
        "display_name": p.display_name,
        "state": p.state,
        "version": p.version,
        "personality_summary": {
            "conviction": p.personality.conviction,
            "warmth": p.personality.warmth,
            "humor": p.personality.humor,
            "directness": p.personality.directness,
        },
        "speech_summary": {
            "interruption_allowed": p.speech.allow_interruption,
            "greeting_preview": p.speech.greeting_text[:60] + "..." if len(p.speech.greeting_text) > 60 else p.speech.greeting_text,
        },
        "tools_enabled": len([t for t in p.tools if t.enabled]),
        "tools_total": len(p.tools),
    }

@router.post("/{profile_id}/test-conversation", response_model=TryItLiveResult)
async def test_conversation(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    _real_integration_required()

@router.post("/{profile_id}/test-tools", response_model=TryItLiveResult)
async def test_tools(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    _real_integration_required()
