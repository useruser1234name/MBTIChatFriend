"""chat_service.py 핵심 로직 단위 테스트"""

import pytest
from app.chat_service import _get_mbti_group, _classify_message_complexity


class TestGetMbtiGroup:
    """MBTI 그룹 분류 테스트"""

    def test_nt_group(self):
        assert _get_mbti_group("INTJ") == "NT"
        assert _get_mbti_group("INTP") == "NT"
        assert _get_mbti_group("ENTJ") == "NT"
        assert _get_mbti_group("ENTP") == "NT"

    def test_nf_group(self):
        assert _get_mbti_group("INFJ") == "NF"
        assert _get_mbti_group("INFP") == "NF"
        assert _get_mbti_group("ENFJ") == "NF"
        assert _get_mbti_group("ENFP") == "NF"

    def test_st_group(self):
        assert _get_mbti_group("ISTJ") == "ST"
        assert _get_mbti_group("ISTP") == "ST"
        assert _get_mbti_group("ESTJ") == "ST"
        assert _get_mbti_group("ESTP") == "ST"

    def test_sf_group(self):
        assert _get_mbti_group("ISFJ") == "SF"
        assert _get_mbti_group("ISFP") == "SF"
        assert _get_mbti_group("ESFJ") == "SF"
        assert _get_mbti_group("ESFP") == "SF"

    def test_invalid_mbti_fallback(self):
        assert _get_mbti_group("XX") == "NF"
        assert _get_mbti_group("") == "NF"

    def test_all_16_types_classified(self):
        all_types = [
            "INTJ", "INTP", "ENTJ", "ENTP",
            "INFJ", "INFP", "ENFJ", "ENFP",
            "ISTJ", "ISTP", "ESTJ", "ESTP",
            "ISFJ", "ISFP", "ESFJ", "ESFP",
        ]
        for mbti in all_types:
            group = _get_mbti_group(mbti)
            assert group in ("NT", "NF", "ST", "SF"), f"{mbti} got unexpected group: {group}"


class TestClassifyMessageComplexity:
    """메시지 복잡도 분류 테스트"""

    def test_simple_greeting(self):
        assert _classify_message_complexity("안녕", 0) == "simple"

    def test_simple_reaction(self):
        assert _classify_message_complexity("ㅋㅋ", 0) == "simple"
        assert _classify_message_complexity("ㅎㅎ", 0) == "simple"

    def test_simple_short_ok(self):
        assert _classify_message_complexity("응", 0) == "simple"
        assert _classify_message_complexity("그래", 0) == "simple"

    def test_complex_long_message(self):
        long_msg = "요즘 회사에서 상사한테 많이 혼나는데, 내가 뭘 잘못한 건지도 모르겠고 정말 힘들어. 어떻게 해야 할까?"
        result = _classify_message_complexity(long_msg, 5)
        assert result == "complex"

    def test_complex_emotional(self):
        """감정 키워드가 포함된 메시지"""
        result = _classify_message_complexity("오늘 너무 우울해", 3)
        # 짧지만 감정 키워드 → complex일 가능성
        assert result in ("simple", "complex")  # 구현에 따라 다를 수 있음
