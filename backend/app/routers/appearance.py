from app.services.vault_client import vault_client
import base64
"""Appearance & Motion panel — full skin editor"""
import os
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File
from pydantic import BaseModel
from app.models import AppearanceConfig, SkinConfig, SkinLighting, SkinDecal, ProfileUpdate, SpeedDoctrine, MotionState, TryItLiveResult
from app.services.profile_service import profile_service
from app.core.security import decode_token

router = APIRouter(prefix="/appearance", tags=["Appearance & Motion"])


class MotionPreviewRequest(BaseModel):
    state: MotionState


class DesktopPresentationUpdate(BaseModel):
    value: dict
    expected_entry_id: str | None = None

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@router.get("/desktop/preferences")
def desktop_preferences(owner=Depends(get_current_owner)):
    return vault_client.call("/presentation/preferences")


@router.put("/desktop/preferences/{profile_id}")
def update_desktop_preferences(profile_id: str, req: DesktopPresentationUpdate, owner=Depends(get_current_owner)):
    if not profile_service.get_profile(profile_id):
        raise HTTPException(404, "Profile not found")
    value = dict(req.value)
    value["profile_id"] = profile_id
    return vault_client.call("/presentation/preferences", {"value": value, "expected_entry_id": req.expected_entry_id})

@router.get("/{profile_id}", response_model=AppearanceConfig)
async def get_appearance(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p.appearance

@router.patch("/{profile_id}", response_model=AppearanceConfig)
async def update_appearance(profile_id: str, config: AppearanceConfig, owner=Depends(get_current_owner)):
    p = profile_service.update_profile(profile_id, ProfileUpdate(appearance=config))
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p.appearance

@router.get("/{profile_id}/skins")
async def get_skins(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"skins": p.appearance.skins, "active": p.appearance.active_skin_id}

@router.post("/{profile_id}/skins")
async def create_skin(profile_id: str, skin: SkinConfig, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    skin.id = str(uuid.uuid4())
    skin.is_factory = False
    skins = p.appearance.skins + [skin]
    updated = p.appearance.model_copy(update={"skins": skins})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"skin_id": skin.id, "name": skin.name}

@router.post("/{profile_id}/skins/upload")
async def upload_skin(profile_id: str, name: str, file: UploadFile = File(...), owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    skin_id = str(uuid.uuid4())
    content = await file.read(4 * 1024 * 1024 + 1)
    if len(content) > 4 * 1024 * 1024:
        raise HTTPException(413, detail="Skin too large")
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, detail="Only PNG, JPEG, and WebP skins are supported")
    skins_data = vault_client.read("skins", {})
    skins_data[skin_id] = {"media_type": file.content_type, "base64": base64.b64encode(content).decode("ascii")}
    vault_client.write("skins", skins_data, "Owner uploaded skin retained in AIMS")
    texture_url = f"data:{file.content_type};base64,{skins_data[skin_id]['base64']}"

    skin = SkinConfig(
        id=skin_id,
        name=name,
        is_factory=False,
        texture_url=texture_url,
    )
    skins = p.appearance.skins + [skin]
    updated = p.appearance.model_copy(update={"skins": skins})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"skin_id": skin.id, "name": skin.name, "url": skin.texture_url}

@router.patch("/{profile_id}/skins/{skin_id}")
async def update_skin(profile_id: str, skin_id: str, skin: SkinConfig, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    skins = []
    for s in p.appearance.skins:
        if s.id == skin_id:
            skins.append(skin)
        else:
            skins.append(s)

    updated = p.appearance.model_copy(update={"skins": skins})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"skin_id": skin_id, "updated": True}

@router.post("/{profile_id}/skins/{skin_id}/activate")
async def activate_skin(profile_id: str, skin_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    skin = next((s for s in p.appearance.skins if s.id == skin_id), None)
    if not skin:
        raise HTTPException(status_code=404, detail="Skin not found")

    updated = p.appearance.model_copy(update={"active_skin_id": skin_id})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"active_skin_id": skin_id, "name": skin.name}

@router.post("/{profile_id}/skins/restore-factory")
async def restore_factory_skin(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    updated = p.appearance.model_copy(update={"active_skin_id": "factory-orb-v1"})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"active_skin_id": "factory-orb-v1", "message": "Factory skin restored"}

@router.post("/{profile_id}/motion-preview")
async def set_motion_preview(profile_id: str, req: MotionPreviewRequest, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    updated = p.appearance.model_copy(update={"motion_preview_state": req.state})
    profile_service.update_profile(profile_id, ProfileUpdate(appearance=updated))
    return {"motion_state": req.state, "previewing": True}

@router.get("/doctrine/speed")
async def speed_doctrine(owner=Depends(get_current_owner)):
    return {
        "doctrine": [
            {"name": SpeedDoctrine.GLIDE, "description": "Default smooth motion. Used always unless visitor signals urgency or runtime failure.", "editable": False},
            {"name": SpeedDoctrine.BRISK, "description": "Faster motion. Only on explicit visitor urgency signal.", "editable": False},
            {"name": SpeedDoctrine.URGENT, "description": "Rapid motion. Only on genuine runtime failure requiring attention.", "editable": False},
        ]
    }

@router.post("/{profile_id}/test-interruption", response_model=TryItLiveResult)
async def test_interruption(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return TryItLiveResult(
        test_type="interruption",
        passed=p.speech.allow_interruption,
        notes=f"Interruption {'enabled' if p.speech.allow_interruption else 'disabled'} at sensitivity {p.speech.interruption_sensitivity}",
    )
