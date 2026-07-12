package com.example.mbtichatfriend.ui.components

import androidx.compose.ui.graphics.Color

/**
 * 호감도 레벨(1~5) → 한국어 관계 명칭 공용 헬퍼 (A2).
 *
 * ChatScreen.kt의 3개 site(헤더 표시, 레벨업 다이얼로그, 레벨다운 다이얼로그)가
 * 레벨 1~5에 대해 완전히 동일한 문자열을 사용하고 있어 통합했다.
 *
 * 주의: HomeScreen.kt의 CharacterCard 내 levelName(레벨 1~5 미표시 시)은
 * else 기본값이 "낯선 사이"로, 이 함수의 else(빈 문자열)와 달라 통합하지 않고
 * 원본 위치에 그대로 유지했다 — A2 보고 참고.
 */
fun affinityLevelName(level: Int): String = when (level) {
    1 -> "낯선 사이"
    2 -> "아는 사이"
    3 -> "친한 친구"
    4 -> "특별한 사이"
    5 -> "연인"
    else -> ""
}

/**
 * 호감도 레벨(1~5) → 카드/온도계 색상 공용 헬퍼 (A2).
 *
 * HomeScreen.kt의 CharacterCard 배지 색상(affinityColor)과
 * AffinityThermometer 구간 색상(levelColor)이 레벨 1~5 및 else 기본값까지
 * 완전히 동일한 색상 값을 사용하고 있어 통합했다.
 */
fun affinityLevelColor(level: Int): Color = when (level) {
    1 -> Color(0xFFB0B0C0)
    2 -> Color(0xFFB5E8D5)
    3 -> Color(0xFFFFF3B0)
    4 -> Color(0xFFFFB5C2)
    5 -> Color(0xFFC9B1FF)
    else -> Color(0xFFB0B0C0)
}

/**
 * 호감도 레벨(1~5) → HomeScreen 카드 배지 태그 텍스트 (A2).
 *
 * affinityLevelName과 문구 체계가 달라(레벨1 = "첫 만남" vs "낯선 사이",
 * 레벨2~5 = "Lv.N" vs 한국어 관계명) 별도 함수로 분리했다.
 * 현재 HomeScreen.kt CharacterCard 1곳에서만 사용.
 */
fun affinityLevelTag(level: Int): String = when (level) {
    1 -> "첫 만남"
    2 -> "Lv.2"
    3 -> "Lv.3"
    4 -> "Lv.4"
    5 -> "Lv.5"
    else -> "첫 만남"
}
