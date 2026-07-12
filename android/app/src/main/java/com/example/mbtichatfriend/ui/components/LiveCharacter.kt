package com.example.mbtichatfriend.ui.components

import android.graphics.RenderEffect
import android.graphics.RuntimeShader
import android.os.Build
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asComposeRenderEffect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.ui.components.EmotionLottieBackground

private const val AGSL_WAVE_SHADER = """
    uniform float2 iResolution;
    uniform float iTime;
    uniform shader contents;

    half4 main(float2 fragCoord) {
        float2 uv = fragCoord / iResolution;

        // 상단(머리카락)에 강한 왜곡, 하단으로 감소
        float strength = smoothstep(0.7, 0.0, uv.y) * 3.0;

        // 사인파 기반 수평 왜곡
        float wave = sin(uv.y * 18.0 + iTime * 2.5) * strength;
        float wave2 = sin(uv.y * 12.0 - iTime * 1.8) * strength * 0.5;

        float2 displaced = fragCoord;
        displaced.x += (wave + wave2);

        return contents.eval(displaced);
    }
"""

/**
 * 유휴(idle) 상태의 캐릭터 모션 파라미터 (C7).
 *
 * 기본값은 리팩토링 이전 [LiveCharacter]의 하드코딩 수치와 정확히 동일하다 —
 * 이 값을 그대로 사용하면(= [motionProfileForMbti]가 매칭 실패로 기본값을 돌려주면)
 * 기존 애니메이션 동작이 100% 보존된다.
 *
 * @param breathScale 숨쉬기 애니메이션의 피크 배율(1.0 기준). 기존 targetValue와 동일.
 * @param floatAmpDp 부유감(TranslationY) 진폭. 기존 targetValue(-8f)의 절댓값과 동일.
 * @param tiltDeg 좌우 틸트 각도(± 범위). 기존 initialValue/targetValue(±0.5f)와 동일.
 * @param speedFactor 애니메이션 속도 배율 — 1.0=현행, 클수록 주기가 짧아져(빨라져) 활발해 보임.
 */
data class MotionProfile(
    val breathScale: Float = 1.025f,
    val floatAmpDp: Float = 8f,
    val tiltDeg: Float = 0.5f,
    val speedFactor: Float = 1.0f,
)

// MBTI 그룹별 배율 상수 (계획서 가이드: E군 진폭·속도 +20%, I군 -15%, 판단형 J 틸트 -30%).
// 전부 기본값 대비 ±30% 이내로 보수적으로 유지.
private const val EXTROVERT_AMPLITUDE_MULTIPLIER = 1.20f
private const val INTROVERT_AMPLITUDE_MULTIPLIER = 0.85f
private const val JUDGING_TILT_MULTIPLIER = 0.70f

/**
 * 캐릭터 MBTI(4글자 코드) → 유휴 모션 프로파일.
 *
 * E/I(1번째 글자)가 숨쉬기 진폭·부유 진폭·속도를 함께 스케일하고,
 * J/P(4번째 글자)가 틸트 각도만 별도로 스케일한다(16종을 E/I × J/P 2축 규칙으로 커버).
 * 형식이 아니거나(4글자 미만) 인식 불가 문자면 [MotionProfile] 기본값(기존 동작)을 반환한다.
 */
fun motionProfileForMbti(mbti: String): MotionProfile {
    val code = mbti.trim().uppercase()
    val base = MotionProfile()
    if (code.length < 4) return base

    val amplitudeMultiplier = when (code[0]) {
        'E' -> EXTROVERT_AMPLITUDE_MULTIPLIER
        'I' -> INTROVERT_AMPLITUDE_MULTIPLIER
        else -> 1.0f
    }
    val tiltMultiplier = if (code[3] == 'J') JUDGING_TILT_MULTIPLIER else 1.0f

    return base.copy(
        breathScale = 1.0f + (base.breathScale - 1.0f) * amplitudeMultiplier,
        floatAmpDp = base.floatAmpDp * amplitudeMultiplier,
        tiltDeg = base.tiltDeg * tiltMultiplier,
        speedFactor = base.speedFactor * amplitudeMultiplier,
    )
}

@Composable
fun LiveCharacter(
    modifier: Modifier = Modifier,
    emotion: CharacterEmotion = CharacterEmotion.NEUTRAL,
    characterSize: Dp = 100.dp,
    enableSensor: Boolean = true,
    motionProfile: MotionProfile = MotionProfile(),
    content: @Composable () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "liveChar")

    // Layer 1: 숨쉬기 (Scale) — 애니메이션 구조(무한 반복+tween+LinearEasing+Reverse) 불변, 스펙 값만 프로파일로 스케일
    val breathScale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue = motionProfile.breathScale,
        animationSpec = infiniteRepeatable(
            animation = tween((2800 / motionProfile.speedFactor).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breath"
    )

    // Layer 1: 부유감 (TranslationY)
    val floatY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -motionProfile.floatAmpDp,
        animationSpec = infiniteRepeatable(
            animation = tween((3400 / motionProfile.speedFactor).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "float"
    )

    // Layer 1: 미세한 회전 (좌우 틸트)
    val tiltZ by infiniteTransition.animateFloat(
        initialValue = -motionProfile.tiltDeg,
        targetValue = motionProfile.tiltDeg,
        animationSpec = infiniteRepeatable(
            animation = tween((4200 / motionProfile.speedFactor).toInt(), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "tilt"
    )

    // 감정별 스케일 반응
    val emotionScale by animateFloatAsState(
        targetValue = when (emotion) {
            CharacterEmotion.HAPPY -> 1.08f
            CharacterEmotion.LOVE -> 1.12f
            CharacterEmotion.ANGRY -> 1.05f
            CharacterEmotion.SURPRISED -> 1.15f
            CharacterEmotion.PLAYFUL -> 1.06f
            CharacterEmotion.WORRIED -> 0.97f
            CharacterEmotion.TOUCHED -> 1.10f
            else -> 1.0f
        },
        animationSpec = spring(stiffness = Spring.StiffnessLow),
        label = "emotionScale"
    )

    // 터치 반동
    var touchBounce by remember { mutableFloatStateOf(1.0f) }
    val animatedBounce by animateFloatAsState(
        targetValue = touchBounce,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessLow
        ),
        label = "bounce"
    )

    // 시차 효과 (Sensor)
    val sensorTilt = if (enableSensor) rememberSensorState() else remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }

    // AGSL Shader 시간 갱신 (API 33+)
    var shaderTime by remember { mutableFloatStateOf(0f) }
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        LaunchedEffect(Unit) {
            val startTime = withFrameMillis { it }
            while (true) {
                withFrameMillis { frameTime ->
                    shaderTime = (frameTime - startTime) / 1000f
                }
            }
        }
    }

    val combinedScale = breathScale * emotionScale * animatedBounce
    val combinedTranslateX = sensorTilt.value.x * 6f
    val combinedTranslateY = floatY + sensorTilt.value.y * 4f

    Box(
        modifier = modifier
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        touchBounce = 0.92f
                        tryAwaitRelease()
                        touchBounce = 1.0f
                    }
                )
            }
            .graphicsLayer {
                scaleX = combinedScale
                scaleY = combinedScale
                translationX = combinedTranslateX
                translationY = combinedTranslateY
                rotationZ = tiltZ
            }
            .then(
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    Modifier.graphicsLayer {
                        val shader = RuntimeShader(AGSL_WAVE_SHADER)
                        shader.setFloatUniform("iResolution", size.width, size.height)
                        shader.setFloatUniform("iTime", shaderTime)
                        renderEffect = RenderEffect
                            .createRuntimeShaderEffect(shader, "contents")
                            .asComposeRenderEffect()
                    }
                } else {
                    Modifier
                }
            ),
        contentAlignment = Alignment.Center
    ) {
        EmotionLottieBackground(
            emotion = emotion,
            modifier = Modifier.size(characterSize)
        )
        content()
    }
}
