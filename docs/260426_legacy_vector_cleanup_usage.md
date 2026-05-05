# Legacy Vector Cleanup

## Purpose
- Inspect Chroma collections without deleting anything by default.
- Delete only explicitly named collections after review.
- Refuse non-legacy candidates unless `--force` is provided.

## Commands
- Report current collections:
  - `python server/admin_legacy_vector_cleanup.py`
- Report as JSON:
  - `python server/admin_legacy_vector_cleanup.py --json`
- Dry-run one exact legacy candidate:
  - `python server/admin_legacy_vector_cleanup.py --collection ep_6`
- Apply deletion for a confirmed legacy candidate:
  - `python server/admin_legacy_vector_cleanup.py --apply --collection ep_6`

## Notes
- The tool compares `char_*/ep_*` collection names against current scoped `room_id` values when PostgreSQL is available.
- Collections that do not match a known scoped room but still contain separators are reported as `unverified_scoped_or_orphan`.
- Only `legacy_global_candidate` collections are deletable without `--force`.
