package com.example.mbtichatfriend.ui.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Shape
import com.example.mbtichatfriend.ui.theme.MotionDurations

/**
 * 자체 구현 스켈레톤 로딩 placeholder (U4).
 *
 * 외부 쉬머 라이브러리를 쓰지 않고 alpha 0.3↔0.7 펄스만으로 로딩 느낌을 낸다
 * (`rememberInfiniteTransition` + `tween`). 화면마다 [Modifier]로 크기/모양을 지정해
 * 실제 콘텐츠 카드의 대략적인 레이아웃을 흉내내는 용도 — 로딩 중 레이아웃 점프를 줄이는 게 목적이라
 * 정확히 같은 크기일 필요는 없다.
 *
 * @param shape 기본값은 U1에서 배선한 [MaterialTheme.shapes]의 small(=AppShapes.small, 12dp) —
 *   원형 아바타 placeholder 등에는 호출부에서 CircleShape 등으로 덮어써서 사용한다.
 */
@Composable
fun SkeletonBox(
    modifier: Modifier = Modifier,
    shape: Shape = MaterialTheme.shapes.small,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "skeletonPulse")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.7f,
        animationSpec = infiniteRepeatable(
            animation = tween(MotionDurations.Medium),
            repeatMode = RepeatMode.Reverse
        ),
        label = "skeletonAlpha"
    )
    Box(
        modifier = modifier
            .clip(shape)
            .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha))
    )
}
