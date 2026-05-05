"""신규 API 엔드포인트 테스트 - mood/checkin, compatibility/check, memory 조회"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import MAX_CONVERSATION_HISTORY, MAX_MESSAGE_LENGTH
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def test_app():
    """FastAPI 앱 생성 + 인증/초기화 의존성 오버라이드"""
    with (
        patch("app.main.init_firebase"),
        patch("app.main.init_storage"),
        patch("app.main.init_postgres_schema"),
        patch("app.main.init_async_pool", new_callable=AsyncMock),
        patch("app.main.close_async_pool", new_callable=AsyncMock),
    ):
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("app.main"):
                del sys.modules[mod_name]

        from app.main import app
        from app.auth_middleware import verify_firebase_token, require_auth_always

        async def _mock_auth():
            return {"uid": "test_user"}

        app.dependency_overrides[verify_firebase_token] = _mock_auth
        app.dependency_overrides[require_auth_always] = _mock_auth

        yield app

        app.dependency_overrides.clear()


# ============================================================
# 1. mood/checkin 테스트
# ============================================================


class TestMoodCheckin:
    """POST /api/v1/mood/checkin 테스트"""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_500(self, test_app):
        """OpenAI API 키 없을 때 500 반환"""
        with patch("app.routers.misc._openai_client", None):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/mood/checkin",
                    json={
                        "mood": "좋아",
                        "character_name": "하루",
                        "mbti": "ENFP",
                        "nickname": "유저",
                    },
                )
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_valid_request_response_structure(self, test_app):
        """정상 요청 시 message, emotion 필드 포함 응답"""
        mock_choice = MagicMock()
        mock_choice.message.content = "오 좋은 하루구나!"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.routers.misc._openai_client", mock_client):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/mood/checkin",
                    json={
                        "mood": "좋아",
                        "character_name": "하루",
                        "mbti": "ENFP",
                        "nickname": "유저",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "emotion" in data
            assert data["emotion"] == "HAPPY"
            assert len(data["message"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_mood_returns_422(self, test_app):
        """유효하지 않은 mood 값이면 422 반환"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/mood/checkin",
                json={
                    "mood": "무효한기분",
                    "character_name": "하루",
                    "mbti": "ENFP",
                    "nickname": "유저",
                },
            )
        assert response.status_code == 422


# ============================================================
# 2. compatibility/check 테스트
# ============================================================


class TestCompatibilityCheck:
    """POST /api/v1/compatibility/check 테스트"""

    @pytest.mark.asyncio
    async def test_valid_mbti_returns_compatibility(self, test_app):
        """유효한 MBTI 조합 요청 시 score/description/strengths/challenges 반환"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "INTJ", "character_mbti": "ENFP"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "description" in data
        assert "strengths" in data
        assert "challenges" in data
        assert isinstance(data["score"], int)
        assert 1 <= data["score"] <= 5
        assert isinstance(data["strengths"], list)
        assert isinstance(data["challenges"], list)
        assert len(data["strengths"]) > 0
        assert len(data["challenges"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_mbti_returns_422(self, test_app):
        """잘못된 MBTI 시 422 반환 (Pydantic 검증)"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "XXXX", "character_mbti": "ENFP"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_mbti_lowercase_returns_422(self, test_app):
        """소문자 MBTI는 패턴 검증에서 422 반환"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "intj", "character_mbti": "enfp"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bidirectional_same_score(self, test_app):
        """양방향 조회 (A,B == B,A) - 동일 점수 확인"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_ab = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "INTJ", "character_mbti": "ESFP"},
            )
            resp_ba = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "ESFP", "character_mbti": "INTJ"},
            )

        assert resp_ab.status_code == 200
        assert resp_ba.status_code == 200
        assert resp_ab.json()["score"] == resp_ba.json()["score"]

    @pytest.mark.asyncio
    async def test_same_mbti_compatibility(self, test_app):
        """동일 MBTI 궁합 조회"""
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/compatibility/check",
                json={"user_mbti": "ENFP", "character_mbti": "ENFP"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["score"], int)


# ============================================================
# 3. memory/{character_name}/{nickname} 테스트
# ============================================================


class TestMemoryGet:
    """GET /api/v1/memory/{character_name}/{nickname} 테스트"""

    @pytest.mark.asyncio
    async def test_nonexistent_character_returns_empty(self, test_app):
        """존재하지 않는 캐릭터 조회 시 빈 결과 반환"""
        with (
            patch("app.routers.memory.get_existing_summary", return_value=""),
            patch("app.routers.memory.get_existing_facts", return_value=[]),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/memory/없는캐릭터/없는유저",
                )

            assert response.status_code == 200
            data = response.json()
            assert data["summary"] == ""
            assert data["facts"] == []
            assert data["total_conversations"] == 0

    @pytest.mark.asyncio
    async def test_response_structure(self, test_app):
        """응답 구조 확인 (summary, facts, total_conversations)"""
        mock_facts = [{"key": "이름", "value": "테스터"}, {"key": "취미", "value": "코딩"}]

        with (
            patch("app.routers.memory.get_existing_summary", return_value="이전에 코딩 이야기를 했었어."),
            patch("app.routers.memory.get_existing_facts", return_value=mock_facts),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/memory/하루/유저",
                )

            assert response.status_code == 200
            data = response.json()
            assert "summary" in data
            assert "facts" in data
            assert "total_conversations" in data
            assert data["summary"] == "이전에 코딩 이야기를 했었어."
            assert len(data["facts"]) == 2
            assert data["facts"][0]["key"] == "이름"
            assert isinstance(data["total_conversations"], int)

    @pytest.mark.asyncio
    async def test_character_id_query_uses_scoped_room_id(self, test_app):
        """character_id 쿼리가 있으면 인증 사용자 room_id만 사용한다."""
        summary_mock = AsyncMock(return_value="요약")
        facts_mock = AsyncMock(return_value=[{"key": "이름", "value": "테스터"}])

        with (
            patch("app.routers.memory.get_existing_summary", new=summary_mock),
            patch("app.routers.memory.get_existing_facts", new=facts_mock),
            patch("app.routers.memory.postgres_enabled", return_value=True),
            patch("app.routers.memory.pg_fetchone", return_value={"cnt": 3}) as fetchone_mock,
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/memory/하루/유저",
                    params={"character_id": "7"},
                )

            assert response.status_code == 200
            summary_mock.assert_awaited_once_with(
                "하루",
                "유저",
                user={"uid": "test_user"},
                room_id="test_user:7",
                character_id="7",
            )
            facts_mock.assert_awaited_once_with(
                "하루",
                "유저",
                user={"uid": "test_user"},
                room_id="test_user:7",
                character_id="7",
            )
            fetchone_mock.assert_called_once_with(
                "SELECT COUNT(*) as cnt FROM metric_events WHERE event_type = 'chat_turn' AND room_id = %s",
                ("test_user:7",),
            )


class TestClientConfig:
    @pytest.mark.asyncio
    async def test_returns_server_constraints(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/config/client")

        assert response.status_code == 200
        assert response.json() == {
            "max_message_length": MAX_MESSAGE_LENGTH,
            "max_conversation_history": MAX_CONVERSATION_HISTORY,
        }


class TestRoomScopeValidation:
    @pytest.mark.asyncio
    async def test_chat_send_rejects_foreign_room_id(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/send",
                json={
                    "message": "안녕",
                    "mbti": "ENFP",
                    "nickname": "테스터",
                    "character_id": "7",
                    "room_id": "other_user:7",
                },
            )

        assert response.status_code == 403
        assert response.json()["detail"] == "room_id does not belong to the authenticated user"

    @pytest.mark.asyncio
    async def test_feedback_rejects_foreign_room_id(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/feedback/submit",
                json={
                    "character_id": "7",
                    "message_id": "11",
                    "feedback_type": "thumbs_up",
                    "room_id": "other_user:7",
                },
            )

        assert response.status_code == 403
        assert response.json()["detail"] == "room_id does not belong to the authenticated user"

    @pytest.mark.asyncio
    async def test_delete_conversation_returns_cleanup_warnings(self, test_app):
        class _DummyCursor:
            def execute(self, query, params):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _DummyConn:
            def cursor(self):
                return _DummyCursor()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with (
            patch("app.routers.data._async_pool_ready", return_value=False),
            patch("app.routers.data.get_conn", return_value=_DummyConn()),
            patch("app.routers.data.record_event"),
            patch("app.routers.data.get_store", return_value=None),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/data/delete-conversation",
                    json={
                        "character_id": "7",
                        "character_name": "하루",
                        "nickname": "테스트",
                    },
                )

        assert response.status_code == 200
        assert response.json()["deleted_targets"] == [
            "story_state",
            "diary_entries",
            "metric_events",
            "response_feedback",
            "conversation_memory",
        ]
        assert response.json()["cleanup_warnings"] == [
            "legacy_global_vector_store_requires_manual_cleanup",
            "legacy_shared_memory_key_requires_manual_cleanup",
        ]


class TestQualityScope:
    @pytest.mark.asyncio
    async def test_dashboard_requires_character_id(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/quality/dashboard")

        assert response.status_code == 400
        assert response.json()["detail"] == "character_id가 필요합니다."

    @pytest.mark.asyncio
    async def test_dashboard_uses_scoped_room_id(self, test_app):
        with patch("app.routers.quality.get_quality_dashboard", return_value={}) as dashboard_mock:
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/quality/dashboard",
                    params={"character_id": "7", "days": 14},
                )

        assert response.status_code == 200
        dashboard_mock.assert_called_once_with("7", 14, room_id="test_user:7")

    @pytest.mark.asyncio
    async def test_diversity_uses_scoped_room_id(self, test_app):
        with patch("app.routers.quality.get_diversity_report", return_value={"warnings": [], "avg_diversity": 1.0}) as diversity_mock:
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/quality/diversity/7")

        assert response.status_code == 200
        diversity_mock.assert_called_once_with("7", room_id="test_user:7")


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_live_health_endpoint(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "kind": "live"}

    @pytest.mark.asyncio
    async def test_ready_health_reports_dependencies(self, test_app):
        with (
            patch("app.main.get_postgres_health", return_value={"status": "ready", "mode": "async_pool"}),
            patch("app.main.get_vector_store_health", return_value={"status": "ready", "initialized": True}),
            patch("app.main.get_storage_health", return_value={"status": "ready", "bucket": "test-bucket"}),
            patch("app.main.snapshot_background_tasks", return_value={"pending": 1, "tasks": {"quality-check": 1}}),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "dependencies": {
                "postgres": {"status": "ready", "mode": "async_pool"},
                "vector_store": {"status": "ready", "initialized": True},
                "storage": {"status": "ready", "bucket": "test-bucket"},
                "background_tasks": {"pending": 1, "tasks": {"quality-check": 1}},
            },
        }

    @pytest.mark.asyncio
    async def test_ready_health_returns_503_on_blocking_dependency(self, test_app):
        with (
            patch("app.main.get_postgres_health", return_value={"status": "error", "mode": "unavailable"}),
            patch("app.main.get_vector_store_health", return_value={"status": "disabled", "initialized": False}),
            patch("app.main.get_storage_health", return_value={"status": "disabled", "bucket": ""}),
            patch("app.main.snapshot_background_tasks", return_value={"pending": 0, "tasks": {}}),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "degraded"


class TestFinetuneOwnership:
    @pytest.mark.asyncio
    async def test_start_passes_owner_uid(self, test_app):
        with patch("app.routers.finetune.prepare_and_start_finetune", new_callable=AsyncMock) as start_mock:
            start_mock.return_value = {
                "job_id": "job-1",
                "status": "queued",
                "training_count": 12,
                "model": "gpt-4.1-mini-2025-04-14",
                "error": "",
            }
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/finetune/start",
                    json={
                        "character_id": "7",
                        "character_name": "하루",
                        "mbti": "ENFP",
                        "speech_style": "SWEET",
                        "relationship": "FRIEND",
                        "nickname": "테스터",
                        "affinity_level": 3,
                        "conversations": [],
                    },
                )

        assert response.status_code == 200
        assert start_mock.await_args.kwargs["owner_uid"] == "test_user"

    @pytest.mark.asyncio
    async def test_status_rejects_foreign_job(self, test_app):
        with patch("app.routers.finetune.check_finetune_status", new=AsyncMock(side_effect=PermissionError("job does not belong to the authenticated user"))):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/finetune/status/job-1")

        assert response.status_code == 403
        assert response.json()["detail"] == "job does not belong to the authenticated user"

    @pytest.mark.asyncio
    async def test_activate_passes_owner_uid(self, test_app):
        with patch("app.routers.finetune.activate_model") as activate_mock:
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/finetune/activate",
                    json={"character_id": "7", "model_id": "ft:test-model"},
                )

        assert response.status_code == 200
        activate_mock.assert_called_once_with("7", "ft:test-model", "test_user")
