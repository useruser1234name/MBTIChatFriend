# 2026-04-26 Server Improvement Meeting

## Format
- Parallel review with 3 agents
- Track 1: config and contract consistency
- Track 2: security and data scoping
- Track 3: operations, lifecycle, and testing

## Decisions Applied
- Made chat message and history limits server-owned in code and tests.
  - `server/app/models.py`
  - `server/app/quality_service.py`
  - `server/tests/test_models.py`
- Published server constraint metadata for Android.
  - `GET /api/v1/config/client`
  - `server/app/routers/misc.py`
  - `server/tests/test_new_apis.py`
- Synced Android local validation upper bounds to the server contract.
  - `android/.../ChatApi.kt`
  - `android/.../RemoteConfigManager.kt`
  - `android/.../MessageConstraints.kt`
- Rejected foreign explicit `room_id` values on stateful server paths.
  - `server/app/scopes.py`
  - `server/app/shared.py`
  - `server/app/routers/data.py`
  - `server/app/routers/quality.py`
- Scoped quality dashboard and diversity analytics by authenticated user room scope instead of raw `character_id`.
  - `server/app/quality_service.py`
  - `server/app/routers/quality.py`
  - `server/tests/test_new_apis.py`
- Added detached background task tracking and graceful shutdown drain.
  - `server/app/background_tasks.py`
  - `server/app/chat_service.py`
  - `server/app/image_service.py`
  - `server/app/main.py`
- Split liveness and readiness health reporting and exposed dependency state.
  - `GET /health/live`
  - `GET /health/ready`
  - `server/app/main.py`
  - `server/app/postgres.py`
  - `server/app/vector_store.py`
  - `server/app/image_service.py`
- Scoped fine-tune job/model ownership by authenticated user.
  - `server/app/finetune_service.py`
  - `server/app/routers/finetune.py`
  - `server/app/chat_service.py`
  - `server/tests/test_new_apis.py`
- Expanded safe conversation-memory cleanup to remove multiple user-scoped key variants during deletion.
  - `server/app/routers/data.py`
- Made legacy cleanup behavior explicit instead of silently touching ambiguous global keys.
  - `server/app/scopes.py`
  - `server/app/models.py`
  - `server/app/routers/data.py`
  - `server/tests/test_scopes.py`
  - `server/tests/test_new_apis.py`
- Added a one-time admin tool for inspecting and explicitly deleting confirmed legacy global Chroma collections.
  - `server/app/legacy_vector_cleanup.py`
  - `server/admin_legacy_vector_cleanup.py`
  - `server/tests/test_legacy_vector_cleanup.py`
- Switched Android validation to UX-only input checks and let server moderation remain authoritative.
  - `android/.../data/local/ContentFilter.kt`
  - `android/.../data/remote/ApiError.kt`
  - `android/.../data/remote/SseClient.kt`
  - `android/.../data/repository/ChatRepository.kt`
  - `android/.../ui/chat/ChatViewModel.kt`
  - `android/.../ui/voicecall/VoiceCallViewModel.kt`
  - `android/.../data/local/OfflineMessageQueue.kt`

## Findings Deferred
- Optional follow-up: wire the admin cleanup output into an internal runbook if this server will be operated by multiple maintainers.

## Validation
- `python -m pytest -q --basetemp=.pytest-tmp-full3`
  - `122 passed, 1 skipped`
- `./gradlew.bat :app:compileDebugKotlin :app:testDebugUnitTest`
  - success
