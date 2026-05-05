"""Helpers for building user-scoped identifiers."""

from __future__ import annotations

from typing import Optional


def _clean_part(value: str) -> str:
    return (value or "").strip().replace(":", "_")


def _validate_explicit_room_id(user: Optional[dict], room_id: str) -> str:
    explicit_room_id = (room_id or "").strip()
    if not explicit_room_id:
        return ""

    uid = ((user or {}).get("uid") or "").strip()
    if not uid:
        return explicit_room_id

    if explicit_room_id == uid or explicit_room_id.startswith(f"{uid}:"):
        return explicit_room_id

    raise ValueError("room_id does not belong to the authenticated user")


def build_room_id(
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
    character_name: str = "",
    mbti: str = "",
) -> str:
    explicit_room_id = _validate_explicit_room_id(user, room_id)
    if explicit_room_id:
        return explicit_room_id

    uid = ((user or {}).get("uid") or "anonymous").strip() or "anonymous"
    character_scope = (
        _clean_part(character_id)
        or _clean_part(character_name)
        or _clean_part(mbti)
        or "unknown"
    )
    return f"{uid}:{character_scope}"


def build_memory_key(
    user: Optional[dict] = None,
    room_id: str = "",
    character_id: str = "",
    character_name: str = "",
    nickname: str = "",
) -> str:
    scoped_room_id = room_id.strip()
    if scoped_room_id:
        return f"room:{scoped_room_id}"

    uid = ((user or {}).get("uid") or "").strip()
    clean_character_id = _clean_part(character_id)
    if uid and clean_character_id:
        return f"user:{uid}:character:{clean_character_id}"

    clean_character_name = _clean_part(character_name)
    clean_nickname = _clean_part(nickname)
    if uid and (clean_character_name or clean_nickname):
        return f"user:{uid}:name:{clean_character_name}:nickname:{clean_nickname}"

    return build_legacy_memory_key(character_name, nickname)


def build_legacy_memory_key(character_name: str, nickname: str) -> str:
    clean_character_name = (character_name or "").strip()
    clean_nickname = (nickname or "").strip()
    if not clean_character_name and not clean_nickname:
        return ""
    return f"{clean_character_name}::{clean_nickname}"


def build_legacy_cleanup_warnings(
    character_id: str = "",
    character_name: str = "",
    nickname: str = "",
) -> list[str]:
    warnings: list[str] = []

    if _clean_part(character_id):
        warnings.append("legacy_global_vector_store_requires_manual_cleanup")

    if build_legacy_memory_key(character_name, nickname):
        warnings.append("legacy_shared_memory_key_requires_manual_cleanup")

    return warnings
