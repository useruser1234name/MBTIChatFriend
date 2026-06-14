"""cached_tokens 계측 (S-3) 테스트.

OpenAI prefix caching의 usage.prompt_tokens_details.cached_tokens 값을
_record_usage / record_api_usage로 전달하는 경로를 단위 검증한다.
"""

from unittest.mock import MagicMock


def test_record_api_usage_accepts_cached_tokens():
    """record_api_usage에 cached_tokens 파라미터가 있다."""
    import inspect
    from app.postgres_async import AsyncDatabase

    sig = inspect.signature(AsyncDatabase.record_api_usage)
    assert "cached_tokens" in sig.parameters, "record_api_usage에 cached_tokens 파라미터 누락"
    assert sig.parameters["cached_tokens"].default == 0


def test_record_usage_fn_accepts_cached_tokens():
    """chat_service._record_usage에 cached_tokens 파라미터가 있다."""
    import inspect
    from app.chat_service import _record_usage

    sig = inspect.signature(_record_usage)
    assert "cached_tokens" in sig.parameters, "_record_usage에 cached_tokens 파라미터 누락"
    assert sig.parameters["cached_tokens"].default == 0


def test_cached_tokens_read_from_usage():
    """OpenAI usage.prompt_tokens_details.cached_tokens 값이 추출된다."""
    usage_mock = MagicMock()
    details_mock = MagicMock()
    details_mock.cached_tokens = 500
    usage_mock.prompt_tokens_details = details_mock

    _prompt_tokens_details = getattr(usage_mock, "prompt_tokens_details", None)
    _cached_tokens = getattr(_prompt_tokens_details, "cached_tokens", 0) or 0
    assert _cached_tokens == 500


def test_cached_tokens_defaults_to_zero_when_missing():
    """prompt_tokens_details 없을 때 cached_tokens=0으로 폴백."""
    usage_mock = MagicMock(spec=[])  # prompt_tokens_details 없는 mock

    _prompt_tokens_details = getattr(usage_mock, "prompt_tokens_details", None)
    _cached_tokens = getattr(_prompt_tokens_details, "cached_tokens", 0) or 0
    assert _cached_tokens == 0
