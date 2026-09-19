from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping
from workspace import AuthoringValidationError, ProtectedAssetError, Workspace, _bundle

def set_presence(workspace: Workspace, actor: str, state: Mapping[str, Any]) -> None:
    workspace.transient["presence"][actor] = deepcopy(dict(state))

def record_transaction(workspace: Workspace, tx_id: str, summary: str) -> None:
    workspace.collaboration["history"].append({"id":tx_id,"summary":summary})

def record_conflict(workspace: Workspace, conflict_id: str, alternatives: list[str]) -> None:
    if len(alternatives) < 2:
        raise AuthoringValidationError("retained alternatives required")
    workspace.collaboration["conflicts"][conflict_id] = {"alternatives":list(alternatives)}

def play(workspace: Workspace) -> str:
    session_id = "play:" + workspace.digest()[:16]
    workspace.transient["play_session"] = {"id":session_id,"revision":workspace.digest()}
    return session_id

def stop(workspace: Workspace) -> None:
    workspace.transient["play_session"] = None

def publish(workspace: Workspace, target: str = "web") -> dict[str, Any]:
    if target not in {"web","native","headless"}:
        raise AuthoringValidationError("unsupported target profile")
    return {"creation_revision":workspace.digest(),"runtime":"generic-player","target_profile":target,"requires_build":False}

def import_asset(workspace: Workspace, asset_id: str, bundle: Mapping[str, Any]) -> None:
    workspace.canonical["assets"][asset_id] = _bundle(bundle)

def replace_asset(workspace: Workspace, asset_id: str, bundle: Mapping[str, Any]) -> None:
    if asset_id not in workspace.canonical["assets"]:
        raise ProtectedAssetError("unknown AssetId")
    workspace.canonical["assets"][asset_id] = _bundle(bundle)

def diagnostic(code: str, subject: str = "item") -> str:
    messages = {
        "known_unloaded": f"{subject} is not loaded yet. Load it to edit or inspect it.",
        "capability_denied": f"{subject} is not allowed to use that device or service.",
        "dependency_unavailable": f"A required reusable part for {subject} is unavailable or incompatible.",
        "conflict": f"{subject} has competing edits. Choose or combine the retained alternatives.",
    }
    return messages.get(code, f"{subject} could not be completed. Open Inspect for SplashMX details.")
