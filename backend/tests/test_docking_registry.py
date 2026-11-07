from app.services.docking_registry import DockingRegistry


def registration(dock_id: str) -> dict:
    return {
        "orb_identity": "orbot",
        "session_id": "session-1",
        "dock_id": dock_id,
        "application_id": dock_id,
        "instance_id": dock_id + "-instance",
        "application_context": {"reference": "fixture"},
        "surface_capabilities": {"voice": True, "controls": True},
        "authorization_scope": ["read"],
    }


def test_registry_allows_one_active_dock_and_increments_generation():
    registry = DockingRegistry()
    first = registry.register(registration("viv-orbot-dock"))
    second = registry.register(registration("communications-orbot-dock"))
    assert first["lease_status"] == "available"
    assert second["lease_status"] == "available"

    transfer = registry.prepare("viv-orbot-dock", {})
    transfer = registry.acknowledge("viv-orbot-dock", transfer["dock_generation"])
    assert transfer["active_dock_id"] == "viv-orbot-dock"
    assert transfer["previous_dock_id"] is None
    first_generation = transfer["dock_generation"]

    transfer = registry.prepare("communications-orbot-dock", {})
    transfer = registry.acknowledge("communications-orbot-dock", transfer["dock_generation"])
    assert transfer["active_dock_id"] == "communications-orbot-dock"
    assert transfer["previous_dock_id"] == "viv-orbot-dock"
    assert transfer["dock_generation"] > first_generation
    status = registry.status()
    assert status["active_dock_id"] == "communications-orbot-dock"
    leases = {dock["dock_id"]: dock["lease_status"] for dock in status["docks"]}
    assert leases == {"viv-orbot-dock": "available", "communications-orbot-dock": "active"}


def test_registry_rejects_unhealthy_transfer_and_releases_active_dock():
    registry = DockingRegistry()
    registry.register(registration("viv-orbot-dock"))
    registry.heartbeat("viv-orbot-dock", "unavailable")
    try:
        registry.prepare("viv-orbot-dock", {})
    except KeyError:
        pass
    else:
        raise AssertionError("unhealthy dock must not acquire the active lease")

    registry.heartbeat("viv-orbot-dock", "ready")
    prepared = registry.prepare("viv-orbot-dock", {})
    registry.acknowledge("viv-orbot-dock", prepared["dock_generation"])
    released = registry.release("viv-orbot-dock")
    assert released["lease_status"] == "available"
    assert registry.status()["active_dock_id"] is None


def test_fencing_is_generation_bound_before_recovery():
    registry = DockingRegistry()
    registry.register(registration("dock-a")); registry.register(registration("dock-b"))
    first = registry.prepare("dock-a", {})
    registry.acknowledge("dock-a", first["dock_generation"])
    prepared = registry.prepare("dock-b", {"party_id": "fixture"})
    registry.acknowledge("dock-b", prepared["dock_generation"])
    registry.heartbeat("dock-b", "unavailable")
    blocked = registry.recover()
    assert blocked["requires_fence"] is True
    registry.fence("dock-b", prepared["dock_generation"])
    recovered = registry.recover()
    assert recovered["recovered"] is True
    assert recovered["active_dock_id"] == "dock-a"
