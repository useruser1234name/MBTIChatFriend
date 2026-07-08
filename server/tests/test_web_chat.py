import pytest
from httpx import Request, Response
from openai import APIStatusError

from app.routers import web_chat
from app.routers.web_chat import WebChatRequest, _build_system_prompt, send_web_chat


@pytest.mark.asyncio
async def test_web_chat_mock_response_without_openai(monkeypatch):
    monkeypatch.setattr(web_chat, "client", None)

    response = await send_web_chat(
        WebChatRequest(
            message="안녕",
            mbti="ENFP",
            persona="장난기 많고 다정한 친구",
            prompt_mode="playful_partner",
        )
    )

    assert response.mocked is True
    assert response.mbti == "ENFP"
    assert response.prompt_mode == "playful_partner"
    assert "ENFP" in response.reply


def test_system_prompt_uses_persona_and_mode_rules():
    prompt = _build_system_prompt(
        mbti="ENFP",
        persona="차가운 외모를 가졌지만 나에게는 따뜻한 북부대공",
        prompt_mode="deep_listener",
    )

    assert "ENFP" in prompt
    assert "차가운 외모를 가졌지만 나에게는 따뜻한 북부대공" in prompt
    assert "Deep listener" in prompt
    assert "Do not turn every reply into advice" in prompt


def test_system_prompt_forbids_literal_persona_explanation():
    prompt = _build_system_prompt(
        mbti="ENFP",
        persona="차가운 외모를 가졌지만 나에게는 따뜻한 북부대공",
        prompt_mode="warm_friend",
    )

    assert "Treat the persona as acting direction" in prompt
    assert "Never explain your own personality" in prompt
    assert "차가운 외모 뒤에 숨겨진 따뜻한 마음으로" in prompt


def test_system_prompt_enables_roleplay_and_actions():
    prompt = _build_system_prompt(
        mbti="ESTJ",
        persona="차가운 외모를 가졌지만 나에게는 따뜻한 북부대공",
        prompt_mode="balanced",
    )

    # 역할극 몰입 + 행동 처리 지침이 있어야 함
    assert "immersive one-on-one chat" in prompt
    assert "interactive roleplay" in prompt
    assert "눈물을 흘린다" in prompt  # 행동 예시
    assert "(조용히 눈물을 닦아주며) 울지 마라" in prompt  # in-character 액션 예시
    # 페르소나 register가 MBTI보다 우선
    assert "outranks generic MBTI" in prompt
    # 위기 안전은 유지
    assert "crisis/self-harm" in prompt


def test_system_prompt_register_matches_persona_not_default_archaic():
    prompt = _build_system_prompt(
        mbti="ENFP",
        persona="따스한 감성을 지닌 여성, 나를 항상 챙겨줌",
        prompt_mode="balanced",
    )

    # 말투는 페르소나에 맞춰야 하고, 기본은 현대 말투 (사극 남발 방지)
    assert "MATCH the persona" in prompt
    assert "modern everyday Korean" in prompt
    assert "NEVER use 사극" in prompt
    # 현대 페르소나 예시 + 사극 오용 Bad 예시가 함께 있어야 함
    assert "다친 덴 없어" in prompt
    assert "WRONG — 사극" in prompt


def test_system_prompt_injects_user_role_and_situation():
    prompt = _build_system_prompt(
        mbti="ESTJ",
        persona="냉정하나 나에게만 따뜻한 북부대공",
        prompt_mode="balanced",
        user_role="나는 대공의 약혼자",
        situation="눈 내리는 겨울 저녁, 대공의 서재",
    )
    assert "Scene — who you are talking to" in prompt
    assert "나는 대공의 약혼자" in prompt
    assert "눈 내리는 겨울 저녁, 대공의 서재" in prompt
    assert "according to THIS relationship" in prompt


def test_system_prompt_has_show_dont_tell_rules():
    prompt = _build_system_prompt(
        mbti="INTJ",
        persona="나를 싫어하는 척하지만 속으론 아는 사람",
        prompt_mode="playful_partner",
    )
    assert "Show, don't tell" in prompt
    # 자기 심리 설명 금지 + 츤데레 지침
    assert "NEVER explain your own feelings" in prompt
    assert "이게 내 방어기제야" in prompt  # 금지 예시
    # 서브텍스트 Good 예시(딴청+행동)
    assert "쓸데없는 소리" in prompt


def test_system_prompt_omits_scene_when_no_role():
    prompt = _build_system_prompt(
        mbti="ENFP",
        persona="다정한 친구",
        prompt_mode="balanced",
    )
    # 역할/상황 미입력 시 Scene 블록은 아예 없어야 함
    assert "Scene — who you are talking to" not in prompt


@pytest.mark.asyncio
async def test_web_chat_rejects_invalid_mbti(monkeypatch):
    monkeypatch.setattr(web_chat, "client", None)

    with pytest.raises(Exception) as exc:
        await send_web_chat(
            WebChatRequest(
                message="안녕",
                mbti="ABCD",
                persona="테스트",
            )
        )

    assert getattr(exc.value, "status_code", None) == 422


@pytest.mark.asyncio
async def test_web_chat_falls_back_on_openai_quota(monkeypatch):
    class _Completions:
        async def create(self, **kwargs):
            raise APIStatusError(
                "insufficient_quota",
                response=Response(
                    429,
                    request=Request("POST", "https://api.openai.com/v1/chat/completions"),
                ),
                body={"error": {"code": "insufficient_quota"}},
            )

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(web_chat, "client", _Client())

    response = await send_web_chat(
        WebChatRequest(
            message="안녕",
            mbti="ENFP",
            persona="다정한 친구",
        )
    )

    assert response.mocked is True
    assert response.model == "mock:openai_quota"
    assert response.prompt_mode == "balanced"
