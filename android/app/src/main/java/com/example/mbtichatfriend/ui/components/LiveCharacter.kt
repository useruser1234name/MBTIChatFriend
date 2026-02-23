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

@Composable
fun LiveCharacter(
    modifier: Modifier = Modifier,
    emotion: CharacterEmotion = CharacterEmotion.NEUTRAL,
    characterSize: Dp = 100.dp,
    enableSensor: Boolean = true,
    content: @Composable () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "liveChar")

    // Layer 1: 숨쉬기 (Scale)
    val breathScale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue = 1.025f,
        animationSpec = infiniteRepeatable(
            animation = tween(2800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breath"
    )

    // Layer 1: 부유감 (TranslationY)
    val floatY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -8f,
        animationSpec = infiniteRepeatable(
            animation = tween(3400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "float"
    )

    // Layer 1: 미세한 회전 (좌우 틸트)
    val tiltZ by infiniteTransition.animateFloat(
        initialValue = -0.5f,
        targetValue = 0.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(4200, easing = LinearEasing),
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
        content()
    }
}
