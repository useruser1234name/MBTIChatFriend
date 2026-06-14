"""편지 생성 (S-9) 테스트.

generate_letter 엔드포인트가 인증을 요구하고, 금지 모델(gpt-4o) 없이
config.LLM_MODEL_BASE로 LLM을 호출하는지 검증한다.
"""

import asyncio
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch


def test_letter_generate_endpoint_has_auth():
    """generate_letter 엔드포인트에 인증(require_auth_always) 의존성이 있다."""
    import inspect
    from app.routers.letter import generate_letter

    sig = inspect.signature(generate_letter)
    assert "user" in sig.parameters, "generate_letter에 user 파라미터(인증) 없음"


def test_letter_no_gpt4o_reference():
    """letter.py 소스코드에 'gpt-4o' / 'GPT-4o' 문자열이 없어야 한다."""
    letter_path = pathlib.Path(__file__).parent.parent / "app" / "routers" / "letter.py"
    source = letter_path.read_text(encoding="utf-8")
    assert "gpt-4o" not in source, "letter.py에 금지 모델(gpt-4o) 참조 발견"
    assert "GPT-4o" not in source, "letter.py에 금지 모델(GPT-4o) 참조 발견"


def test_letter_uses_llm_model_base_config():
    """generate_letter가 config.LLM_MODEL_BASE를 사용한다."""
    letter_path = pathlib.Path(__file__).parent.parent / "app" / "routers" / "letter.py"
    source = letter_path.read_text(encoding="utf-8")
    assert "LLM_MODEL_BASE" in source, "letter.py에 LLM_MODEL_BASE 사용 없음"


def test_letter_generate_uses_llm_mock():
    """mock OpenAI 클라이언트로 generate_letter가 LLM 호출하는지 검증."""
    from app.routers.letter import generate_letter, LetterRequest

    req = LetterRequest(
        room_id="uid1:char1",
        character_id="char1",
        user_id="uid1",
        top_topic="여행",
    )

    db_mock = MagicMock()
    db_mock.available = False  # DB 없어도 LLM 경로 동작

    choice_mock = MagicMock()
    choice_mock.message.content = "여행 이야기가 정말 좋았어. 또 얘기하자."
    completion_mock = MagicMock()
    completion_mock.choices = [choice_mock]

    openai_client_mock = MagicMock()
    openai_client_mock.chat.completions.create = AsyncMock(return_value=completion_mock)

    async def run():
        with (
            patch("app.routers.letter.get_async_db", return_value=db_mock),
            patch("app.routers.letter.OPENAI_API_KEY", "fake-key"),
            patch("openai.AsyncOpenAI", return_value=openai_client_mock),
        ):
            return await generate_letter(req=req, user={"uid": "uid1"})

    result = asyncio.run(run())
    assert "content" in result
    assert result["content"] != ""
    assert "expires_at" in result
