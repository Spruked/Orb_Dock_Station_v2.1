"""Intelligence & Models panel — full model selector"""
import time
from starlette.concurrency import run_in_threadpool
from app.services.vault_client import vault_client
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Header
from app.models import IntelligenceConfig, ModelLane, ModelConfig, ProfileUpdate, ModelTestResult
from app.services.profile_service import profile_service
from app.services.health_monitor import health_monitor
from app.core.security import decode_token

router = APIRouter(prefix="/intelligence", tags=["Intelligence & Models"])

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/{profile_id}", response_model=IntelligenceConfig)
async def get_intelligence(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p.intelligence

@router.patch("/{profile_id}", response_model=IntelligenceConfig)
async def update_intelligence(profile_id: str, config: IntelligenceConfig, owner=Depends(get_current_owner)):
    p = profile_service.update_profile(profile_id, ProfileUpdate(intelligence=config))
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p.intelligence

@router.get("/{profile_id}/lanes")
async def get_lanes(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"lanes": p.intelligence.lanes, "active": p.intelligence.active_lane}

@router.patch("/{profile_id}/lanes/{lane_name}")
async def update_lane(profile_id: str, lane_name: str, config: ModelConfig, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    lanes = []
    for lane in p.intelligence.lanes:
        if lane.name == lane_name:
            lanes.append(lane.model_copy(update={"config": config}))
        else:
            lanes.append(lane)

    updated = p.intelligence.model_copy(update={"lanes": lanes})
    profile_service.update_profile(profile_id, ProfileUpdate(intelligence=updated))
    return {"lane": lane_name, "updated": True}

@router.post("/{profile_id}/lanes/{lane_name}/activate")
async def activate_lane(profile_id: str, lane_name: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    lane = next((l for l in p.intelligence.lanes if l.name == lane_name), None)
    if not lane:
        raise HTTPException(status_code=404, detail="Lane not found")

    updated = p.intelligence.model_copy(update={"active_lane": lane_name})
    profile_service.update_profile(profile_id, ProfileUpdate(intelligence=updated))
    return {"active_lane": lane_name, "provider": lane.config.provider, "model": lane.config.model_id}

@router.post("/{profile_id}/lanes/{lane_name}/test")
async def test_lane_connection(profile_id: str, lane_name: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    lane = next((l for l in p.intelligence.lanes if l.name == lane_name), None)
    if not lane:
        raise HTTPException(status_code=404, detail="Lane not found")

    # Probe only the existing Communication runtime, never an arbitrary draft URL.
    started = time.perf_counter()
    state = await run_in_threadpool(vault_client.call, "/status")
    models = state.get("models", [])
    matches = (lane.config.provider == "llama.cpp" and
               lane.config.model_id.lower() in " ".join(models).lower() and
               bool(state.get("llm_connected")))
    return ModelTestResult(
        lane_name=lane_name, passed=matches,
        latency_ms=round((time.perf_counter()-started)*1000), ttf_ms=None,
        sample_output="Loaded models: " + ", ".join(models),
        error=None if matches else "Draft provider/model does not match the connected runtime, or model unavailable",
    )

@router.post("/{profile_id}/lanes/{lane_name}/test-response")
async def test_lane_response(profile_id: str, lane_name: str, prompt: str = "Say hello briefly.", owner=Depends(get_current_owner)):
    raise HTTPException(501, "Draft model response testing is not connected to Orbot's governed conversation path. No inference was performed.")

@router.post("/{profile_id}/restore-recommended")
async def restore_recommended(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Reset to seed configuration
    from app.services.profile_service import ProfileService
    seed = ProfileService()._create_seed_profile()
    updated = p.intelligence.model_copy(update={
        "lanes": seed.intelligence.lanes,
        "active_lane": "universal",
        "fallback_enabled": True,
        "deterministic_fallback": True,
    })
    profile_service.update_profile(profile_id, ProfileUpdate(intelligence=updated))
    return {"restored": True, "active_lane": "universal"}

@router.get("/health/gateway")
async def gateway_health(owner=Depends(get_current_owner)):
    return health_monitor.get_gateway_report()
