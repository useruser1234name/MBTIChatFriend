package com.example.mbtichatfriend.ui.chat

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.airbnb.lottie.compose.*

/**
 * 호감도 레벨(1~5)에 따라 다른 Lottie 애니메이션을 표시하는 컴포저블.
 * AffinityManager.levelUpEvent 트리거 시 애니메이션 재생.
 *
 * 사용: ChatScreen에서 levelUpEvent를 collect하여 isAnimating = true 전달.
 */
@Composable
fun LottieAffinityView(
    affinityLevel: Int,
    isAnimating: Boolean,
    modifier: Modifier = Modifier,
) {
    // 레벨별 Lottie 애니메이션 raw resource 매핑
    // 실제 JSON 파일은 res/raw/affinity_level_1.json ~ affinity_level_5.json
    val rawRes = when (affinityLevel.coerceIn(1, 5)) {
        1 -> "affinity_level_1"
        2 -> "affinity_level_2"
        3 -> "affinity_level_3"
        4 -> "affinity_level_4"
        else -> "affinity_level_5"
    }

    val composition by rememberLottieComposition(
        LottieCompositionSpec.Asset("lottie/$rawRes.json")
    )
    val progress by animateLottieCompositionAsState(
        composition = composition,
        isPlaying = isAnimating,
        restartOnPlay = true,
        iterations = 1,
    )

    if (isAnimating || progress > 0f) {
        LottieAnimation(
            composition = composition,
            progress = { progress },
            modifier = modifier
                .size(120.dp)
                .padding(8.dp),
        )
    }
}
