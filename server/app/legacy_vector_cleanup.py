"""Helpers for inspecting and safely cleaning legacy Chroma collections."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional, Sequence

from .postgres import fetchall, postgres_enabled
from .vector_store import CHROMA_AVAILABLE, VectorStore

STATUS_ACTIVE_SCOPED = "active_scoped"
STATUS_LEGACY_GLOBAL_CANDIDATE = "legacy_global_candidate"
STATUS_UNVERIFIED_SCOPED_OR_ORPHAN = "unverified_scoped_or_orphan"
STATUS_UNKNOWN = "unknown"

_COLLECTION_PREFIXES = (
    ("char_", "memory"),
    ("ep_", "episode"),
)


@dataclass(frozen=True)
class CollectionReport:
    name: str
    collection_type: str
    status: str
    matched_room_id: str = ""
    note: str = ""


def _normalize_collection_names(collections: Iterable[Any]) -> list[str]:
    names: list[str] = []
    for item in collections:
        name = item if isinstance(item, str) else getattr(item, "name", "")
        if name:
            names.append(str(name))
    return sorted(dict.fromkeys(names))


def list_collection_names(persist_dir: str) -> list[str]:
    if not CHROMA_AVAILABLE:
        return []

    store = VectorStore(persist_dir=persist_dir)
    try:
        return _normalize_collection_names(store.client.list_collections())
    finally:
        store.close()


def load_known_room_ids() -> tuple[set[str], str]:
    if not postgres_enabled():
        return set(), "disabled"

    room_ids: set[str] = set()
    queries = [
        "SELECT DISTINCT room_id FROM story_state WHERE room_id <> ''",
        "SELECT DISTINCT room_id FROM diary_entries WHERE room_id <> ''",
        "SELECT DISTINCT room_id FROM metric_events WHERE room_id IS NOT NULL AND room_id <> ''",
        "SELECT DISTINCT room_id FROM response_feedback WHERE room_id <> ''",
    ]

    try:
        for query in queries:
            for row in fetchall(query):
                room_id = str(row.get("room_id") or "").strip()
                if room_id:
                    room_ids.add(room_id)

        for row in fetchall(
            "SELECT DISTINCT memory_key FROM conversation_memory WHERE memory_key LIKE %s",
            ("room:%",),
        ):
            memory_key = str(row.get("memory_key") or "").strip()
            if memory_key.startswith("room:"):
                room_id = memory_key[len("room:"):].strip()
                if room_id:
                    room_ids.add(room_id)

        return room_ids, "available"
    except Exception as exc:
        return set(), f"error:{exc}"


def _build_expected_collection_map(known_room_ids: Iterable[str]) -> dict[str, tuple[str, str]]:
    expected: dict[str, tuple[str, str]] = {}
    for room_id in known_room_ids:
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            continue
        expected[VectorStore._safe_name("char_", normalized_room_id)] = ("memory", normalized_room_id)
        expected[VectorStore._safe_name("ep_", normalized_room_id)] = ("episode", normalized_room_id)
    return expected


def classify_collection_name(
    name: str,
    expected_collections: Optional[dict[str, tuple[str, str]]] = None,
) -> CollectionReport:
    expected = expected_collections or {}
    if name in expected:
        collection_type, room_id = expected[name]
        return CollectionReport(
            name=name,
            collection_type=collection_type,
            status=STATUS_ACTIVE_SCOPED,
            matched_room_id=room_id,
            note="Matches a known scoped room_id.",
        )

    for prefix, collection_type in _COLLECTION_PREFIXES:
        if not name.startswith(prefix):
            continue

        suffix = name[len(prefix):]
        if "_" not in suffix:
            return CollectionReport(
                name=name,
                collection_type=collection_type,
                status=STATUS_LEGACY_GLOBAL_CANDIDATE,
                note="Suffix has no scoped room_id separator after sanitization.",
            )

        return CollectionReport(
            name=name,
            collection_type=collection_type,
            status=STATUS_UNVERIFIED_SCOPED_OR_ORPHAN,
            note="Does not match a known active room_id. Review manually before deletion.",
        )

    return CollectionReport(
        name=name,
        collection_type="unknown",
        status=STATUS_UNKNOWN,
        note="Outside managed char_/ep_ prefixes.",
    )


def inspect_vector_store(
    persist_dir: str,
    known_room_ids: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    if known_room_ids is None:
        resolved_room_ids, db_status = load_known_room_ids()
    else:
        resolved_room_ids = {str(room_id or "").strip() for room_id in known_room_ids if str(room_id or "").strip()}
        db_status = "provided"

    expected = _build_expected_collection_map(resolved_room_ids)
    reports = [
        classify_collection_name(name, expected)
        for name in list_collection_names(persist_dir)
    ]
    reports.sort(key=lambda item: (item.status, item.name))

    summary: dict[str, int] = {}
    for report in reports:
        summary[report.status] = summary.get(report.status, 0) + 1

    return {
        "persist_dir": persist_dir,
        "db_status": db_status,
        "known_room_ids": sorted(resolved_room_ids),
        "collections": [asdict(report) for report in reports],
        "summary": summary,
    }


def delete_named_collections(
    persist_dir: str,
    collection_names: Sequence[str],
    *,
    known_room_ids: Optional[Iterable[str]] = None,
    apply: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    inspection = inspect_vector_store(persist_dir, known_room_ids=known_room_ids)
    by_name = {item["name"]: item for item in inspection["collections"]}

    requested = sorted(dict.fromkeys(name.strip() for name in collection_names if name.strip()))
    result: dict[str, Any] = {
        "persist_dir": persist_dir,
        "apply": apply,
        "force": force,
        "requested": requested,
        "planned": [],
        "deleted": [],
        "skipped": [],
        "inspection_summary": inspection["summary"],
    }

    allowed_to_delete: list[str] = []
    for name in requested:
        report = by_name.get(name)
        if report is None:
            result["skipped"].append({"name": name, "reason": "not_found"})
            continue

        if report["status"] != STATUS_LEGACY_GLOBAL_CANDIDATE and not force:
            result["skipped"].append({
                "name": name,
                "reason": f"refusing_non_legacy_status:{report['status']}",
            })
            continue

        allowed_to_delete.append(name)
        if not apply:
            result["planned"].append({"name": name, "status": report["status"]})

    if not apply or not allowed_to_delete or not CHROMA_AVAILABLE:
        return result

    store = VectorStore(persist_dir=persist_dir)
    try:
        for name in allowed_to_delete:
            try:
                store.client.delete_collection(name)
                result["deleted"].append(name)
            except Exception as exc:
                result["skipped"].append({"name": name, "reason": f"delete_failed:{exc}"})
    finally:
        store.close()

    return result
