"""Inspect and safely clean legacy global Chroma collections.

Examples:
    python admin_legacy_vector_cleanup.py
    python admin_legacy_vector_cleanup.py --collection ep_6
    python admin_legacy_vector_cleanup.py --apply --collection ep_6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.legacy_vector_cleanup import delete_named_collections, inspect_vector_store


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and safely clean legacy global Chroma collections.",
    )
    parser.add_argument(
        "--persist-dir",
        default=str(Path(__file__).resolve().parent / "chroma_db"),
        help="Path to the Chroma persistence directory.",
    )
    parser.add_argument(
        "--collection",
        action="append",
        default=[],
        help="Exact collection name to inspect for deletion. Repeat to target multiple collections.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the explicitly requested collections.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow deleting explicitly named collections even when they are not classified as legacy_global_candidate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser


def _render_inspection(data: dict[str, Any]) -> str:
    lines = [
        f"persist_dir: {data['persist_dir']}",
        f"db_status: {data['db_status']}",
        f"known_room_ids: {len(data['known_room_ids'])}",
        f"collections: {len(data['collections'])}",
    ]
    if data["summary"]:
        lines.append(f"summary: {data['summary']}")
    for item in data["collections"]:
        detail = f"{item['name']} [{item['collection_type']}] {item['status']}"
        if item.get("matched_room_id"):
            detail += f" room_id={item['matched_room_id']}"
        if item.get("note"):
            detail += f" | {item['note']}"
        lines.append(detail)
    return "\n".join(lines)


def _render_deletion(data: dict[str, Any]) -> str:
    lines = [
        f"persist_dir: {data['persist_dir']}",
        f"apply: {data['apply']}",
        f"force: {data['force']}",
        f"requested: {data['requested']}",
    ]
    if data["planned"]:
        lines.append(f"planned: {data['planned']}")
    if data["deleted"]:
        lines.append(f"deleted: {data['deleted']}")
    if data["skipped"]:
        lines.append(f"skipped: {data['skipped']}")
    return "\n".join(lines)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.apply and not args.collection:
        parser.error("--apply requires at least one --collection value")

    if args.collection:
        result = delete_named_collections(
            args.persist_dir,
            args.collection,
            apply=args.apply,
            force=args.force,
        )
        output = json.dumps(result, ensure_ascii=False, indent=2) if args.json else _render_deletion(result)
    else:
        result = inspect_vector_store(args.persist_dir)
        output = json.dumps(result, ensure_ascii=False, indent=2) if args.json else _render_inspection(result)

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
