package com.example.mbtichatfriend.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * 앱 공용 Shapes 토큰 (U1).
 *
 * M3 기본 Shapes(extraSmall=4dp, small=8dp, medium=12dp, large=16dp, extraLarge=28dp)보다
 * 전반적으로 더 둥근 값을 사용한다 — 기존 화면 곳곳에서 이미 16~20dp 코너를 리터럴로
 * 쓰고 있던 것과 톤을 맞추기 위함(Theme.kt에 배선하기 전까지 M3 기본값이 쓰이고 있었음).
 *
 * 주의: shape을 명시하지 않은 M3 컴포넌트(Card/Button/TextField/BottomSheet/Dialog 등)는
 * 이 토큰이 MaterialTheme.shapes로 배선되는 순간 아래 대응 단계를 참조하게 된다.
 * 변화량이 큰 컴포넌트는 개별적으로 명시적 shape을 지정해 현상을 유지했다 — U1 보고 참고.
 */
val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(24.dp)
)
