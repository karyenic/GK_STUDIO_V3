# -*- coding: utf-8 -*-
"""
GK Studio V3 - Conversation Store

Normal sohbetler:
    <studio>/chat_history/*.json

RAG / Workspace sohbetleri:
    <project>/.gk_studio/conversation.json

Amaç, proje sohbetlerinin normal/model sohbet geçmişine hiç yazılmamasıdır.
"""
import json
import os
import time
from typing import Any, Dict, Tuple


def _safe_conversation(conversation: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(conversation or {})
    safe["isGenerating"] = False
    safe.pop("abortCtrl", None)
    return safe


def _atomic_json_write(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


def project_conversation_path(project_path: str) -> str:
    return os.path.join(project_path, ".gk_studio", "conversation.json")


def load_project_conversations(project_path: str) -> Dict[str, Any]:
    path = project_conversation_path(project_path)
    if not os.path.exists(path):
        return {
            "project_name": "",
            "conversations": {},
            "currentConvId": None,
            "nextId": 1,
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "project_name": data.get("project_name", ""),
            "conversations": data.get("conversations", {}) or {},
            "currentConvId": data.get("currentConvId"),
            "nextId": data.get("nextId", 1) or 1,
        }
    except (OSError, json.JSONDecodeError):
        return {
            "project_name": "",
            "conversations": {},
            "currentConvId": None,
            "nextId": 1,
        }


def save_project_conversations(
    project_path: str,
    project_name: str,
    conversations: Dict[str, Any],
    current_conv_id: str = None,
    next_id: int = 1,
) -> None:
    project_convs = {}
    for cid, conv in (conversations or {}).items():
        safe = _safe_conversation(conv)
        safe["projectName"] = project_name
        project_convs[str(cid)] = safe

    payload = {
        "version": 1,
        "project_name": project_name,
        "updated_at": time.time(),
        "conversations": project_convs,
        "currentConvId": str(current_conv_id) if current_conv_id in project_convs else None,
        "nextId": int(next_id or 1),
    }
    _atomic_json_write(project_conversation_path(project_path), payload)


def migrate_legacy_project_conversations(
    base_dir: str,
    projects_config: Dict[str, Any],
) -> Tuple[int, int]:
    """
    Eski chat_history içindeki projectName taşıyan sohbetleri, proje yolu
    biliniyorsa ilgili .gk_studio/conversation.json dosyasına taşır.

    Return:
        (moved_count, skipped_unknown_project_count)
    """
    if not projects_config:
        return 0, 0

    moved = 0
    skipped = 0
    grouped: Dict[str, Dict[str, Any]] = {}

    chat_dir = os.path.join(base_dir, "chat_history")
    if not os.path.isdir(chat_dir):
        return 0, 0

    for fn in os.listdir(chat_dir):
        if not fn.endswith(".json"):
            continue

        path = os.path.join(chat_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        conversations = data.get("conversations", {}) or {}
        for cid, conv in conversations.items():
            if not isinstance(conv, dict):
                continue

            project_name = str(conv.get("projectName") or "").strip()
            if not project_name:
                continue

            if project_name not in projects_config:
                skipped += 1
                continue

            grouped.setdefault(project_name, {})[str(cid)] = _safe_conversation(conv)

    for project_name, conversations in grouped.items():
        proj = projects_config.get(project_name) or {}
        project_path = str(proj.get("path") or "").strip()
        if not project_path or not os.path.isdir(project_path):
            skipped += len(conversations)
            continue

        existing = load_project_conversations(project_path)
        merged = dict(existing.get("conversations", {}) or {})
        for cid, conv in conversations.items():
            merged[cid] = conv

        save_project_conversations(
            project_path=project_path,
            project_name=project_name,
            conversations=merged,
            current_conv_id=existing.get("currentConvId"),
            next_id=existing.get("nextId", 1),
        )
        moved += len(conversations)

    return moved, skipped


def load_global_conversations(chat_dir: str) -> Dict[str, Any]:
    all_convs: Dict[str, Any] = {}
    latest_id = None
    max_id = 1

    os.makedirs(chat_dir, exist_ok=True)

    for fn in os.listdir(chat_dir):
        if not fn.endswith(".json"):
            continue

        path = os.path.join(chat_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        for cid, conv in (data.get("conversations", {}) or {}).items():
            if not isinstance(conv, dict):
                continue

            # Güvenlik bariyeri: eski RAG sohbetleri global geçmişe geri dönmez.
            if str(conv.get("projectName") or "").strip():
                continue

            safe = _safe_conversation(conv)
            all_convs[str(cid)] = safe

        current = data.get("currentConvId")
        if current and str(current) in all_convs:
            latest_id = str(current)

        try:
            max_id = max(max_id, int(data.get("nextId", 1) or 1))
        except (TypeError, ValueError):
            pass

    return {
        "conversations": all_convs,
        "currentConvId": latest_id,
        "nextId": max_id,
    }


def save_global_conversations(
    chat_dir: str,
    conversations: Dict[str, Any],
    current_conv_id: str = None,
    next_id: int = 1,
) -> None:
    groups: Dict[str, Dict[str, Any]] = {}

    for cid, conv in (conversations or {}).items():
        if not isinstance(conv, dict):
            continue

        # Proje sohbetleri normal/model geçmişine ASLA yazılmaz.
        if str(conv.get("projectName") or "").strip():
            continue

        safe = _safe_conversation(conv)
        model = str(safe.get("model") or "default_model")
        model = model.replace(":", "_").replace("\\", "_").replace("/", "_")

        groups.setdefault(model, {})[str(cid)] = safe

    os.makedirs(chat_dir, exist_ok=True)

    for model, group in groups.items():
        cur = str(current_conv_id) if str(current_conv_id) in group else None
        _atomic_json_write(
            os.path.join(chat_dir, f"{model}.json"),
            {
                "version": 2,
                "conversations": group,
                "currentConvId": cur,
                "nextId": int(next_id or 1),
            },
        )
