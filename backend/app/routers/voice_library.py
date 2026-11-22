from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.core.security import decode_token
from app.models import ProfileUpdate
from app.services.profile_service import profile_service
from app.services.voice_library import voice_library
from fastapi import Header, HTTPException

router = APIRouter(prefix="/voice-library", tags=["Voice Library"])

def owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer ") or not decode_token(authorization.split(" ", 1)[1]):
        raise HTTPException(401, "Owner authentication required")

@router.get("")
async def list_voices(_=Depends(owner)):
    return {"voices": voice_library.list(), "storage": str(voice_library.root), "engine": "VoiceStudio/OmniVoice"}

@router.get("/{voice_id}/preview")
async def preview(voice_id: str, _=Depends(owner)):
    return FileResponse(voice_library.preview_path(voice_id), media_type="audio/wav")

@router.post("/import")
async def import_voice(name: str = Form(...), file: UploadFile = File(...), _=Depends(owner)):
    return await voice_library.import_sample(file, name)

@router.post("/{profile_id}/select/{voice_id}")
async def select_voice(profile_id: str, voice_id: str, _=Depends(owner)):
    voice = voice_library.get(voice_id)
    if not voice: raise HTTPException(404, "Voice is not in the Dock Station library")
    if voice.get("status") != "synthesizable" or not voice.get("profile_id"):
        raise HTTPException(409, "Voice is preview-only until a compatible OmniVoice profile is verified")
    profile = profile_service.get_profile(profile_id)
    if not profile: raise HTTPException(404, "Profile not found")
    speech = profile.speech.model_copy(update={"voice_id": voice_id, "voice_profile_id": voice["profile_id"]})
    updated = profile_service.update_profile(profile_id, ProfileUpdate(speech=speech))
    return {"selected": updated.speech.voice_id, "voice_profile_id": updated.speech.voice_profile_id}
