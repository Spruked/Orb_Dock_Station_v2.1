from app.services.vault_client import vault_client
"""Profile service — Draft/Published lifecycle, versions, diff"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.models import (
    OrbProfile, ProfileState, ProfileVersion, ProfileCreate, ProfileUpdate,
    OrbChannel, PersonalityBlend, SpeechSettings, IntelligenceConfig,
    ToolEntry, AppearanceConfig, DeploymentTarget, ModelLane, StageDirective,
    ModelConfig, SkinConfig, SkinLighting, MotionState, SpeedDoctrine
)

class ProfileService:
    def __init__(self):
        pass

    def _load_profiles(self) -> Dict[str, dict]:
        return vault_client.read("profiles", {})

    def _save_profiles(self, data: Dict[str, dict]):
        vault_client.write("profiles", data, "Owner profile configuration retained")

    def _load_versions(self) -> List[dict]:
        return vault_client.read("versions", [])

    def _save_versions(self, data: List[dict]):
        vault_client.write("versions", data, "Profile version history retained")

    def _ensure_seed(self):
        profiles = self._load_profiles()
        if not profiles:
            seed = self._create_seed_profile()
            profiles[seed.id] = self._profile_to_dict(seed)
            self._save_profiles(profiles)
            self._record_version(seed, "Initial seed profile")

    def _create_seed_profile(self) -> OrbProfile:
        return OrbProfile(
            id=str(uuid.uuid4()), name="orbot-desktop", display_name="Orbot Desktop",
            channel=OrbChannel.DESKTOP, state=ProfileState.DRAFT, version=1,
            intelligence=IntelligenceConfig(
                lanes=[ModelLane(name="local", config=ModelConfig(
                    endpoint="http://127.0.0.1:16520/v1", healthy=False))],
                active_lane="local", fallback_enabled=False),
            appearance=AppearanceConfig(skins=[SkinConfig(
                id="orbot-red-blue", name="Orbot Red / Blue", is_factory=True,
                base_color="#a91922", secondary_color="#265aff")],
                active_skin_id="orbot-red-blue"),
            speech=SpeechSettings(greeting_text="Hello. I am Orbot."),
        )

    def _profile_to_dict(self, p: OrbProfile) -> dict:
        return json.loads(p.model_dump_json())

    def _dict_to_profile(self, d: dict) -> OrbProfile:
        return OrbProfile(**d)

    def list_profiles(self) -> List[OrbProfile]:
        self._ensure_seed()
        data = self._load_profiles()
        return [self._dict_to_profile(v) for v in data.values()]

    def get_profile(self, profile_id: str) -> Optional[OrbProfile]:
        data = self._load_profiles()
        p = data.get(profile_id)
        return self._dict_to_profile(p) if p else None

    def get_published_profile(self, name: str, channel: OrbChannel) -> Optional[OrbProfile]:
        for p in self.list_profiles():
            if p.name == name and p.channel == channel and p.state == ProfileState.PUBLISHED:
                return p
        return None

    def create_profile(self, req: ProfileCreate) -> OrbProfile:
        profiles = self._load_profiles()
        profile = OrbProfile(
            id=str(uuid.uuid4()),
            name=req.name,
            display_name=req.display_name,
            channel=req.channel,
            state=ProfileState.DRAFT,
            version=1,
        )
        profiles[profile.id] = self._profile_to_dict(profile)
        self._save_profiles(profiles)
        self._record_version(profile, "Profile created")
        return profile

    def update_profile(self, profile_id: str, req: ProfileUpdate) -> Optional[OrbProfile]:
        profiles = self._load_profiles()
        p = profiles.get(profile_id)
        if not p:
            return None

        if p.get("state") == ProfileState.PUBLISHED:
            p["state"] = ProfileState.DRAFT
            p["version"] = p.get("version", 1) + 1

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                p[key] = value

        p["updated_at"] = datetime.utcnow().isoformat()
        profiles[profile_id] = p
        self._save_profiles(profiles)
        return self._dict_to_profile(p)

    def publish_profile(self, profile_id: str, summary: str = "", owner: str = "owner") -> Optional[OrbProfile]:
        profiles = self._load_profiles()
        p = profiles.get(profile_id)
        if not p:
            return None

        for pid, other in profiles.items():
            if other["name"] == p["name"] and other["channel"] == p["channel"] and other["state"] == ProfileState.PUBLISHED and pid != profile_id:
                other["state"] = ProfileState.DRAFT

        p["state"] = ProfileState.PUBLISHED
        p["published_at"] = datetime.utcnow().isoformat()
        p["updated_at"] = datetime.utcnow().isoformat()
        profiles[profile_id] = p
        self._save_profiles(profiles)
        self._record_version(self._dict_to_profile(p), summary, published_by=owner)
        return self._dict_to_profile(p)

    def restore_version(self, profile_id: str, version: int) -> Optional[OrbProfile]:
        versions = self._load_versions()
        for v in versions:
            if v["profile_id"] == profile_id and v["version"] == version:
                profiles = self._load_profiles()
                snapshot = v["snapshot"]
                snapshot["state"] = ProfileState.DRAFT
                snapshot["version"] = (profiles.get(profile_id, {}).get("version", 1) or 1) + 1
                snapshot["updated_at"] = datetime.utcnow().isoformat()
                profiles[profile_id] = snapshot
                self._save_profiles(profiles)
                self._record_version(self._dict_to_profile(snapshot), f"Restored from version {version}")
                return self._dict_to_profile(snapshot)
        return None

    def get_versions(self, profile_id: str) -> List[ProfileVersion]:
        versions = self._load_versions()
        result = []
        for v in versions:
            if v["profile_id"] == profile_id:
                result.append(ProfileVersion(**v))
        return sorted(result, key=lambda x: x.version, reverse=True)

    def diff_profile(self, profile_id: str) -> Dict[str, Any]:
        versions = self._load_versions()
        profiles = self._load_profiles()
        current = profiles.get(profile_id, {})

        published_versions = [v for v in versions if v["profile_id"] == profile_id and v["state"] == "published"]
        if not published_versions:
            return {"has_diff": True, "changes": ["New profile — no published version exists yet."]}

        last_published = max(published_versions, key=lambda x: x["version"])
        changes = []

        for key in ["personality", "speech", "intelligence", "appearance", "tools", "stage_directives", "prohibited_patterns"]:
            if current.get(key) != last_published["snapshot"].get(key):
                changes.append(f"{key} modified")

        return {"has_diff": len(changes) > 0, "changes": changes, "last_published_version": last_published["version"]}

    def _record_version(self, profile: OrbProfile, summary: str, published_by: Optional[str] = None):
        versions = self._load_versions()
        versions.append({
            "profile_id": profile.id,
            "version": profile.version,
            "state": profile.state,
            "snapshot": self._profile_to_dict(profile),
            "created_at": datetime.utcnow().isoformat(),
            "published_by": published_by,
            "change_summary": summary,
        })
        self._save_versions(versions)

profile_service = ProfileService()

