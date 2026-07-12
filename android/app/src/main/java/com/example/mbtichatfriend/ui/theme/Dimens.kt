package com.example.mbtichatfriend.ui.theme

import androidx.compose.ui.unit.dp

/**
 * 공용 spacing 토큰 (U1).
 *
 * 기존 코드는 padding/spacing 값을 화면마다 리터럴(dp)로 직접 박아 넣고 있었다.
 * 이 객체는 새 토큰 "정의"만 제공한다 — 기존 리터럴의 일괄 치환은 이번 항목의
 * 범위가 아니며, U2 이후 각 항목이 실제로 손대는 파일에서만 점진적으로 적용한다.
 */
object Spacing {
    val xs = 4.dp
    val sm = 8.dp
    val md = 12.dp
    val lg = 16.dp
    val xl = 24.dp
    val xxl = 32.dp
}
