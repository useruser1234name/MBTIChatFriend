"""Pydantic 모델 검증 테스트"""

import pytest
from app.config import MAX_CONVERSATION_HISTORY, MAX_MESSAGE_LENGTH
from pydantic import ValidationError
from app.models import ChatRequest, HistoryMessage, MemoryItem


class TestChatRequest:
    """ChatRequest 입력 검증 테스트"""

    def test_valid_request(self):
        req = ChatRequest(
            message="안녕하세요",
            mbti="ENFP",
            nickname="테스터"
        )
        assert req.message == "안녕하세요"
        assert req.mbti == "ENFP"
        assert req.speech_style == "CASUAL"
        assert req.affinity_level == 1

    def test_message_min_length(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="", mbti="ENFP", nickname="테스터")

    def test_message_max_length(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="a" * (MAX_MESSAGE_LENGTH + 1), mbti="ENFP", nickname="테스터")

    def test_message_at_max_length(self):
        """최대 길이는 통과해야 함"""
        req = ChatRequest(message="가" * MAX_MESSAGE_LENGTH, mbti="ENFP", nickname="테스터")
        assert len(req.message) == MAX_MESSAGE_LENGTH

    def test_invalid_mbti_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="XXXX", nickname="테스터")

    def test_invalid_mbti_format(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="enfp", nickname="테스터")

    def test_valid_mbti_types(self):
        valid = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
                 "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
        for mbti in valid:
            req = ChatRequest(message="안녕", mbti=mbti, nickname="테스터")
            assert req.mbti == mbti

    def test_xss_sanitize(self):
        req = ChatRequest(message="<script>alert('xss')</script>", mbti="ENFP", nickname="테스터")
        assert "<" not in req.message
        assert "&lt;" in req.message

    def test_speech_style_validation(self):
        req = ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", speech_style="FORMAL")
        assert req.speech_style == "FORMAL"

    def test_invalid_speech_style(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", speech_style="INVALID")

    def test_affinity_level_range(self):
        req = ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", affinity_level=5)
        assert req.affinity_level == 5

    def test_affinity_level_too_high(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", affinity_level=6)

    def test_affinity_level_too_low(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", affinity_level=0)

    def test_conversation_history_max_length(self):
        """50턴 이하만 허용"""
        history = [HistoryMessage(role="user", content=f"msg {i}") for i in range(MAX_CONVERSATION_HISTORY + 1)]
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", conversation_history=history)

    def test_conversation_history_at_limit(self):
        history = [HistoryMessage(role="user", content=f"msg {i}") for i in range(MAX_CONVERSATION_HISTORY)]
        req = ChatRequest(message="안녕", mbti="ENFP", nickname="테스터", conversation_history=history)
        assert len(req.conversation_history) == MAX_CONVERSATION_HISTORY

    def test_nickname_max_length(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="안녕", mbti="ENFP", nickname="a" * 21)


class TestHistoryMessage:
    def test_valid_message(self):
        msg = HistoryMessage(role="user", content="안녕하세요")
        assert msg.role == "user"

    def test_assistant_role(self):
        msg = HistoryMessage(role="assistant", content="반가워요")
        assert msg.role == "assistant"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            HistoryMessage(role="system", content="test")
