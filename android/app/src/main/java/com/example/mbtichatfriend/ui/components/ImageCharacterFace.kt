package com.example.mbtichatfriend.ui.components

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import coil.compose.AsyncImage
import com.example.mbtichatfriend.model.CharacterEmotion
import kotlinx.coroutines.delay

/**
 * 이미지 기반 캐릭터 렌더러.
 *
 * 전체 이미지 교체 방식으로 표정 전환, 눈깜빡임, 입 움직임 구현.
 * - 기본 상태: 현재 감정에 맞는 전체 이미지
 * - 깜빡임: 감정 이미지 → eyes_closed 이미지 → 감정 이미지 (260ms)
 * - 대화 중: mouth_small/medium/open 이미지를 120ms 간격 교체
 */
@Composable
fun ImageCharacterFace(
    baseImageUrl: String,
    expressionUrls: Map<String, String>?,
    emotion: CharacterEmotion,
    isTalking: Boolean,
    modifier: Modifier = Modifier
) {
    // 표정 세트가 없으면 기본 이미지만 표시
    if (expressionUrls == null) {
        AsyncImage(
            model = baseImageUrl,
            contentDescription = "캐릭터 이미지",
            modifier = modifier.clip(CircleShape),
            contentScale = ContentScale.Crop
        )
        return
    }

    // 현재 감정에 해당하는 이미지 URL
    val emotionKey = emotionToKey(emotion)
    val emotionUrl = expressionUrls[emotionKey] ?: baseImageUrl

    // 눈깜빡임 상태: 0=normal, 1=eyes_half_closed, 2=eyes_closed
    var blinkState by remember { mutableIntStateOf(0) }

    // 입 움직임 상태
    val mouthKeys = listOf("mouth_small", "mouth_medium", "mouth_open", "mouth_medium")
    var mouthIndex by remember { mutableIntStateOf(0) }

    // 눈깜빡임 애니메이션 (3~6초 랜덤 간격)
    LaunchedEffect(Unit) {
        while (true) {
            delay(3000L + (Math.random() * 3000).toLong())
            // eyes_half_closed → eyes_closed → eyes_half_closed → normal
            blinkState = 1
            delay(80)
            blinkState = 2
            delay(100)
            blinkState = 1
            delay(80)
            blinkState = 0
        }
    }

    // 입 움직임 애니메이션 (대화 중일 때만)
    LaunchedEffect(isTalking) {
        if (!isTalking) {
            mouthIndex = -1
            return@LaunchedEffect
        }
        mouthIndex = 0
        while (true) {
            delay(120)
            mouthIndex = (mouthIndex + 1) % mouthKeys.size
        }
    }

    // 현재 표시할 이미지 결정 (우선순위: 깜빡임 > 입 움직임 > 감정)
    val currentUrl = when {
        blinkState == 2 -> expressionUrls["eyes_closed"] ?: emotionUrl
        blinkState == 1 -> expressionUrls["eyes_half_closed"] ?: emotionUrl
        isTalking && mouthIndex >= 0 -> {
            val mouthKey = mouthKeys[mouthIndex]
            expressionUrls[mouthKey] ?: emotionUrl
        }
        else -> emotionUrl
    }

    Box(modifier = modifier) {
        Crossfade(
            targetState = currentUrl,
            animationSpec = tween(durationMillis = 80),
            label = "character_face"
        ) { url ->
            AsyncImage(
                model = url,
                contentDescription = "캐릭터 표정",
                modifier = Modifier.clip(CircleShape),
                contentScale = ContentScale.Crop
            )
        }
    }
}

private fun emotionToKey(emotion: CharacterEmotion): String {
    return when (emotion) {
        CharacterEmotion.NEUTRAL -> "neutral"
        CharacterEmotion.HAPPY -> "happy"
        CharacterEmotion.SAD -> "sad"
        CharacterEmotion.ANGRY -> "angry"
        CharacterEmotion.SHY -> "shy"
        CharacterEmotion.SURPRISED -> "surprised"
        CharacterEmotion.LOVE -> "love"
        CharacterEmotion.PLAYFUL -> "playful"
        CharacterEmotion.WORRIED -> "worried"
        CharacterEmotion.TOUCHED -> "touched"
    }
}
