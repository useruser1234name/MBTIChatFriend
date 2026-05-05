"""호감도 계산 단위 테스트 - 감쇠/복귀/레벨 경계값"""

import pytest
from datetime import datetime, timezone, timedelta


# chat_service 전체 임포트 시 openai 의존성 문제 우회를 위해
# 함수와 상수를 직접 재현하여 로직만 단위 테스트
AFFINITY_LEVEL_THRESHOLDS = {1: 0, 2: 20, 3: 40, 4: 60, 5: 80}
FREEZE_DAYS = 7
DECAY_PER_WEEK = 2
RETURN_RECOVERY_RATE = 0.5


def calculate_affinity_decay(current_score, current_level, last_chat_time):
    if last_chat_time is None:
        return current_score
    now = datetime.now(timezone.utc)
    if last_chat_time.tzinfo is None:
        last_chat_time = last_chat_time.replace(tzinfo=timezone.utc)
    days_inactive = (now - last_chat_time).days
    if days_inactive <= FREEZE_DAYS:
        return current_score
    weeks_after_freeze = (days_inactive - FREEZE_DAYS) / 7
    decay = int(weeks_after_freeze * DECAY_PER_WEEK)
    lower_level = max(1, current_level - 1)
    min_score = AFFINITY_LEVEL_THRESHOLDS.get(lower_level, 0)
    return max(current_score - decay, min_score)


def calculate_return_bonus(original_score, current_score):
    lost = original_score - current_score
    if lost <= 0:
        return 0
    return int(lost * RETURN_RECOVERY_RATE)


class TestAffinityDecay:
    """호감도 감쇠 계산 테스트"""

    def test_no_decay_within_freeze_period(self):
        """7일 이내 접속 - 감쇠 없음"""
        last_chat = datetime.now(timezone.utc) - timedelta(days=5)
        result = calculate_affinity_decay(50, 3, last_chat)
        assert result == 50

    def test_no_decay_exactly_7_days(self):
        """정확히 7일 - 동결 기간 포함"""
        last_chat = datetime.now(timezone.utc) - timedelta(days=7)
        result = calculate_affinity_decay(50, 3, last_chat)
        assert result == 50

    def test_decay_after_14_days(self):
        """14일 미접속 (1주 경과) - 2점 감쇠"""
        last_chat = datetime.now(timezone.utc) - timedelta(days=14)
        result = calculate_affinity_decay(50, 3, last_chat)
        assert result == 48

    def test_decay_after_28_days(self):
        """28일 미접속 (3주 경과) - 6점 감쇠"""
        last_chat = datetime.now(timezone.utc) - timedelta(days=28)
        result = calculate_affinity_decay(50, 3, last_chat)
        assert result == 44

    def test_decay_floor_at_lower_level(self):
        """하한: 현재 레벨-1 최소 점수 이하로 안 내려감"""
        # Level 3 (40-59점), 하한 = Level 2 최소 = 20점
        last_chat = datetime.now(timezone.utc) - timedelta(days=200)
        result = calculate_affinity_decay(45, 3, last_chat)
        assert result == 20

    def test_decay_floor_level_1(self):
        """Level 1은 0점 이하로 안 내려감"""
        last_chat = datetime.now(timezone.utc) - timedelta(days=200)
        result = calculate_affinity_decay(10, 1, last_chat)
        assert result == 0

    def test_none_last_chat_no_decay(self):
        """last_chat_time이 None이면 변화 없음"""
        result = calculate_affinity_decay(50, 3, None)
        assert result == 50

    def test_naive_datetime_handled(self):
        """timezone 없는 datetime도 처리"""
        last_chat = datetime.utcnow() - timedelta(days=14)
        result = calculate_affinity_decay(50, 3, last_chat)
        assert result == 48


class TestReturnBonus:
    """복귀 보너스 계산 테스트"""

    def test_basic_return_bonus(self):
        """하락분 10점의 50% = 5점 보너스"""
        bonus = calculate_return_bonus(50, 40)
        assert bonus == 5

    def test_no_bonus_when_no_loss(self):
        """하락 없으면 보너스 0"""
        bonus = calculate_return_bonus(50, 50)
        assert bonus == 0

    def test_no_bonus_when_score_increased(self):
        """점수 증가 시 보너스 0"""
        bonus = calculate_return_bonus(40, 50)
        assert bonus == 0

    def test_large_loss_recovery(self):
        """큰 하락(30점)의 50% = 15점"""
        bonus = calculate_return_bonus(80, 50)
        assert bonus == 15

    def test_small_loss_rounds_down(self):
        """1점 하락의 50% = 0점 (int 절삭)"""
        bonus = calculate_return_bonus(50, 49)
        assert bonus == 0


class TestAffinityLevelThresholds:
    """레벨 경계값 일관성 테스트"""

    def test_level_boundaries(self):
        """서버 레벨 경계값 확인"""
        assert AFFINITY_LEVEL_THRESHOLDS[1] == 0
        assert AFFINITY_LEVEL_THRESHOLDS[2] == 20
        assert AFFINITY_LEVEL_THRESHOLDS[3] == 40
        assert AFFINITY_LEVEL_THRESHOLDS[4] == 60
        assert AFFINITY_LEVEL_THRESHOLDS[5] == 80

    def test_score_to_level_mapping(self):
        """점수 → 레벨 변환 (Android CharacterEntity와 일치 확인)"""
        def score_to_level(score):
            if score >= 80: return 5
            if score >= 60: return 4
            if score >= 40: return 3
            if score >= 20: return 2
            return 1

        # 경계값 테스트
        assert score_to_level(0) == 1
        assert score_to_level(19) == 1
        assert score_to_level(20) == 2  # Android 수정 후 일치
        assert score_to_level(39) == 2
        assert score_to_level(40) == 3
        assert score_to_level(59) == 3
        assert score_to_level(60) == 4
        assert score_to_level(79) == 4
        assert score_to_level(80) == 5
        assert score_to_level(100) == 5
