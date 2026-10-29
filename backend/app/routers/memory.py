from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.routers.profiles import get_current_owner
from app.services.vault_client import vault_client

router = APIRouter(prefix="/memory", tags=["AIMS sessions"])


@router.post("/start")
def start(owner=Depends(get_current_owner)):
    return vault_client.call("/sessions", {})


class EndSession(BaseModel):
    session_id: str


@router.post("/end")
def end(req: EndSession, owner=Depends(get_current_owner)):
    return vault_client.call("/sessions/end", {"session_id": req.session_id})
