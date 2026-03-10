package com.example.mbtichatfriend.ui.components

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import com.airbnb.lottie.compose.LottieAnimation
import com.airbnb.lottie.compose.LottieCompositionSpec
import com.airbnb.lottie.compose.LottieConstants
import com.airbnb.lottie.compose.rememberLottieComposition
import com.example.mbtichatfriend.model.CharacterEmotion

/**
 * Maps [CharacterEmotion] to a Lottie asset and renders it as a translucent
 * background layer with a smooth crossfade when the emotion changes.
 */
@Composable
fun EmotionLottieBackground(
    emotion: CharacterEmotion,
    modifier: Modifier = Modifier,
    alpha: Float = 0.30f
) {
    Crossfade(
        targetState = emotion,
        animationSpec = tween(400),
        label = "emotionLottieCrossfade",
        modifier = modifier
    ) { targetEmotion ->
        val assetPath = emotionToLottieAsset(targetEmotion)
        val composition by rememberLottieComposition(LottieCompositionSpec.Asset(assetPath))

        LottieAnimation(
            composition = composition,
            iterations = LottieConstants.IterateForever,
            modifier = Modifier
                .fillMaxSize()
                .alpha(alpha)
        )
    }
}

/**
 * Resolves a [CharacterEmotion] to the corresponding Lottie JSON asset path
 * under `assets/lottie/`.
 *
 * Fallback logic:
 * - SHY      -> shy.json  (fallback idle.json)
 * - SURPRISED -> surprised.json (fallback idle.json)
 * - PLAYFUL  -> playful.json (fallback happy.json)
 */
private fun emotionToLottieAsset(emotion: CharacterEmotion): String = when (emotion) {
    CharacterEmotion.HAPPY     -> "lottie/happy.json"
    CharacterEmotion.ANGRY     -> "lottie/angry.json"
    CharacterEmotion.LOVE,
    CharacterEmotion.TOUCHED   -> "lottie/love.json"
    CharacterEmotion.SAD,
    CharacterEmotion.WORRIED   -> "lottie/sad.json"
    CharacterEmotion.SHY       -> "lottie/shy.json"       // fallback: idle.json
    CharacterEmotion.SURPRISED -> "lottie/surprised.json"  // fallback: idle.json
    CharacterEmotion.PLAYFUL   -> "lottie/playful.json"    // fallback: happy.json
    CharacterEmotion.NEUTRAL   -> "lottie/idle.json"
}
