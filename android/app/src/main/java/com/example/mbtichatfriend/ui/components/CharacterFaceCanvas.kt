package com.example.mbtichatfriend.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.ui.layout.ContentScale
import coil.compose.AsyncImage
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.model.CharacterAvatar
import com.example.mbtichatfriend.model.CharacterEmotion
import kotlinx.coroutines.delay
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * 아바타 렌더러.
 * avatarId가 "v2:..." 형식이면 Compose Canvas로 캐릭터 얼굴을 그리고,
 * 그렇지 않으면 구형 이모지 + 색상 원을 보여줌.
 */
@Composable
fun CharacterFace(
    avatarId: String,
    modifier: Modifier = Modifier,
    emotion: CharacterEmotion = CharacterEmotion.NEUTRAL,
    legacyFontSize: Float = 22f,
    expressionUrls: Map<String, String>? = null,
    isTalking: Boolean = false
) {
    if (avatarId.startsWith("img:")) {
        val imageUrl = avatarId.removePrefix("img:")
        ImageCharacterFace(
            baseImageUrl = imageUrl,
            expressionUrls = expressionUrls,
            emotion = emotion,
            isTalking = isTalking,
            modifier = modifier
        )
    } else if (avatarId.startsWith("v2:")) {
        val config = AvatarConfig.fromId(avatarId)

        // 눈 깜빡임: 3~5초 주기
        var isBlinking by remember { mutableStateOf(false) }
        val blinkInterval = remember(emotion) {
            when (emotion) {
                CharacterEmotion.HAPPY, CharacterEmotion.LOVE -> 5000L
                else -> 3500L
            }
        }
        LaunchedEffect(emotion, blinkInterval) {
            while (true) {
                delay(blinkInterval + (Math.random() * 1500).toLong())
                isBlinking = true
                delay(120)
                isBlinking = false
            }
        }

        Canvas(modifier = modifier) {
            drawCharacterFace(config, emotion, isBlinking)
        }
    } else {
        val avatar = CharacterAvatar.fromId(avatarId)
        Box(
            modifier = modifier
                .clip(CircleShape)
                .background(Color(avatar.colorHex).copy(alpha = 0.4f)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = avatar.emoji,
                fontSize = legacyFontSize.sp,
                textAlign = TextAlign.Center
            )
        }
    }
}

// ─────────────────────────────────────────────────────────
// 내부 Canvas 그리기 함수들
// ─────────────────────────────────────────────────────────

private fun DrawScope.drawCharacterFace(
    config: AvatarConfig,
    emotion: CharacterEmotion,
    isBlinking: Boolean
) {
    val w  = size.width
    val h  = size.height
    val cx = w / 2f
    val cy = h / 2f

    val skin = config.skinColor
    val hair = config.hairColorValue

    // 0. 배경 원
    drawCircle(color = Color(config.bgColor).copy(alpha = 0.65f))

    // 1. 헤어 뒷레이어
    drawHairBack(config.hairStyle, hair, cx, cy, w, h)

    // 2. 귀 (얼굴보다 뒤, 헤어 앞)
    val faceR  = w * 0.33f
    val faceCy = cy + h * 0.04f
    drawCircle(skin, radius = faceR * 0.27f, center = Offset(cx - faceR * 0.9f, faceCy))
    drawCircle(skin, radius = faceR * 0.27f, center = Offset(cx + faceR * 0.9f, faceCy))

    // 3. 얼굴
    drawCircle(skin, radius = faceR, center = Offset(cx, faceCy))

    // 4. 앞머리 (얼굴 위에 올림)
    drawBangs(config.hairStyle, hair, cx, cy, w, h)

    // 5. 눈썹
    drawEyebrows(hair, cx, faceCy, faceR, w, emotion)

    // 6. 속눈썹 라인
    drawEyelashes(cx, faceCy, faceR, w)

    // 7. 눈
    drawEyes(config.eyeStyle, cx, faceCy, faceR, w, emotion, isBlinking)

    // 8. 코
    drawNose(cx, faceCy, faceR, w)

    // 9. 볼 터치
    if (config.blushEnabled || emotion == CharacterEmotion.SHY || emotion == CharacterEmotion.LOVE) {
        val intensity = when (emotion) {
            CharacterEmotion.SHY -> 0.45f
            CharacterEmotion.LOVE -> 0.40f
            else -> 0.30f
        }
        val bc = Color(0xFFFF6B9D)
        drawCircle(bc.copy(alpha = intensity), radius = w * 0.085f,
            center = Offset(cx - faceR * 0.65f, faceCy + faceR * 0.24f))
        drawCircle(bc.copy(alpha = intensity), radius = w * 0.085f,
            center = Offset(cx + faceR * 0.65f, faceCy + faceR * 0.24f))
        // 빗금 볼터치 (SHY/LOVE)
        if (emotion == CharacterEmotion.SHY || emotion == CharacterEmotion.LOVE) {
            val lineColor = Color(0xFFFF6B9D).copy(alpha = 0.25f)
            val lineStroke = w * 0.008f
            for (side in listOf(-1f, 1f)) {
                val bCx = cx + side * faceR * 0.65f
                val bCy = faceCy + faceR * 0.24f
                for (i in -2..2) {
                    val offset = i * w * 0.018f
                    drawLine(
                        lineColor,
                        Offset(bCx + offset - w * 0.025f, bCy - w * 0.03f),
                        Offset(bCx + offset + w * 0.025f, bCy + w * 0.03f),
                        strokeWidth = lineStroke
                    )
                }
            }
        }
    }

    // 10. 입
    drawMouth(cx, faceCy, faceR, w, emotion)

    // 11. 감정별 추가 이펙트
    drawEmotionEffects(emotion, cx, faceCy, faceR, w)

    // 12. 악세서리
    if (config.accessory > 0) {
        drawAccessory(config.accessory, hair, cx, cy, faceCy, faceR, w, h)
    }
}

// ── 헤어 뒷레이어 ──────────────────────────────────────────

private fun DrawScope.drawHairBack(style: Int, color: Color, cx: Float, cy: Float, w: Float, h: Float) {
    val hcy = cy - h * 0.02f
    when (style) {
        0 -> { // 긴 생머리
            drawRoundRect(color,
                topLeft = Offset(cx - w * 0.36f, hcy - h * 0.42f),
                size    = Size(w * 0.72f, h * 0.90f),
                cornerRadius = CornerRadius(w * 0.36f))
            // 머리카락 하이라이트
            drawHairHighlight(cx - w * 0.12f, hcy - h * 0.10f, w * 0.06f, h * 0.35f, color)
        }
        1 -> { // 단발
            drawRoundRect(color,
                topLeft = Offset(cx - w * 0.36f, hcy - h * 0.42f),
                size    = Size(w * 0.72f, h * 0.58f),
                cornerRadius = CornerRadius(w * 0.3f))
            drawHairHighlight(cx - w * 0.10f, hcy - h * 0.08f, w * 0.05f, h * 0.25f, color)
        }
        2 -> { // 트윈테일
            drawCircle(color, radius = w * 0.4f, center = Offset(cx, hcy))
            drawOval(color, topLeft = Offset(cx - w * 0.5f,  cy + h * 0.04f), size = Size(w * 0.22f, h * 0.42f))
            drawOval(color, topLeft = Offset(cx + w * 0.28f, cy + h * 0.04f), size = Size(w * 0.22f, h * 0.42f))
        }
        3 -> { // 포니테일
            drawCircle(color, radius = w * 0.4f, center = Offset(cx, hcy))
            drawOval(color, topLeft = Offset(cx + w * 0.2f, cy - h * 0.52f), size = Size(w * 0.24f, h * 0.30f))
        }
        4 -> { // 짧은 머리
            drawCircle(color, radius = w * 0.40f, center = Offset(cx, hcy - h * 0.03f))
        }
        5 -> { // 올림머리
            drawCircle(color, radius = w * 0.4f,  center = Offset(cx, hcy))
            drawCircle(color, radius = w * 0.18f, center = Offset(cx, hcy - h * 0.42f))
        }
    }
}

// ── 머리카락 하이라이트 ─────────────────────────────────────

private fun DrawScope.drawHairHighlight(x: Float, y: Float, w: Float, h: Float, baseColor: Color) {
    val highlight = Color.White.copy(alpha = 0.18f)
    val path = Path().apply {
        moveTo(x, y)
        quadraticTo(x + w * 0.5f, y + h * 0.3f, x + w * 0.2f, y + h)
        quadraticTo(x - w * 0.3f, y + h * 0.7f, x, y)
        close()
    }
    drawPath(path, highlight)
}

// ── 앞머리 ─────────────────────────────────────────────────

private fun DrawScope.drawBangs(style: Int, color: Color, cx: Float, cy: Float, w: Float, h: Float) {
    when (style) {
        0 -> { // 긴 - 직선 앞머리 + 갈래 분리선
            drawRoundRect(color,
                topLeft = Offset(cx - w * 0.30f, cy - h * 0.42f),
                size    = Size(w * 0.60f, h * 0.22f),
                cornerRadius = CornerRadius(w * 0.06f))
            // 앞머리 분리선
            val sepColor = Color.Black.copy(alpha = 0.08f)
            val sepStroke = w * 0.006f
            drawLine(sepColor, Offset(cx - w * 0.08f, cy - h * 0.40f), Offset(cx - w * 0.10f, cy - h * 0.22f), strokeWidth = sepStroke)
            drawLine(sepColor, Offset(cx + w * 0.08f, cy - h * 0.40f), Offset(cx + w * 0.10f, cy - h * 0.22f), strokeWidth = sepStroke)
        }
        1 -> { // 단발
            drawRoundRect(color,
                topLeft = Offset(cx - w * 0.27f, cy - h * 0.42f),
                size    = Size(w * 0.54f, h * 0.22f),
                cornerRadius = CornerRadius(w * 0.06f))
            val sepColor = Color.Black.copy(alpha = 0.08f)
            drawLine(sepColor, Offset(cx, cy - h * 0.40f), Offset(cx - w * 0.02f, cy - h * 0.22f), strokeWidth = w * 0.006f)
        }
        2 -> { // 트윈테일 - 중앙 가르마
            drawRoundRect(color,
                topLeft = Offset(cx - w * 0.20f, cy - h * 0.42f),
                size    = Size(w * 0.40f, h * 0.19f),
                cornerRadius = CornerRadius(w * 0.06f))
        }
        3 -> { // 포니테일 - 옆 가르마
            drawOval(color,
                topLeft = Offset(cx - w * 0.30f, cy - h * 0.42f),
                size    = Size(w * 0.38f, h * 0.21f))
        }
        4 -> { // 짧은 - 뾰족한 앞머리
            for (i in -1..1) {
                val sx = cx + i * w * 0.10f
                val path = Path().apply {
                    moveTo(sx - w * 0.06f, cy - h * 0.35f)
                    lineTo(sx, cy - h * 0.44f)
                    lineTo(sx + w * 0.06f, cy - h * 0.35f)
                    close()
                }
                drawPath(path, color)
            }
        }
        5 -> { // 올림머리
            drawOval(color,
                topLeft = Offset(cx - w * 0.19f, cy - h * 0.42f),
                size    = Size(w * 0.38f, h * 0.16f))
        }
    }
}

// ── 눈썹 ───────────────────────────────────────────────────

private fun DrawScope.drawEyebrows(
    hairColor: Color, cx: Float, faceCy: Float, faceR: Float, w: Float,
    emotion: CharacterEmotion
) {
    val browColor  = Color(hairColor.red * 0.7f, hairColor.green * 0.7f, hairColor.blue * 0.7f, 1f)
    val browY      = faceCy - faceR * 0.44f
    val browX      = faceR * 0.38f
    val browStroke = Stroke(width = w * 0.028f, cap = StrokeCap.Round)

    when (emotion) {
        CharacterEmotion.ANGRY -> {
            // V자 눈썹 (안쪽이 내려감)
            for (sign in listOf(-1f, 1f)) {
                val path = Path().apply {
                    moveTo(cx + sign * (browX + w * 0.06f), browY + w * 0.025f)
                    lineTo(cx + sign * (browX - w * 0.04f), browY - w * 0.020f)
                }
                drawPath(path, browColor, style = browStroke)
            }
        }
        CharacterEmotion.SAD -> {
            // 팔자 눈썹 (바깥이 올라감)
            for (sign in listOf(-1f, 1f)) {
                val path = Path().apply {
                    moveTo(cx + sign * (browX - w * 0.05f), browY - w * 0.015f)
                    quadraticTo(
                        cx + sign * browX, browY + w * 0.015f,
                        cx + sign * (browX + w * 0.05f), browY - w * 0.008f
                    )
                }
                drawPath(path, browColor, style = browStroke)
            }
        }
        CharacterEmotion.WORRIED -> {
            // ∩ 형태 눈썹
            for (sign in listOf(-1f, 1f)) {
                val path = Path().apply {
                    moveTo(cx + sign * (browX - w * 0.05f), browY + w * 0.012f)
                    quadraticTo(
                        cx + sign * browX, browY - w * 0.025f,
                        cx + sign * (browX + w * 0.05f), browY + w * 0.012f
                    )
                }
                drawPath(path, browColor, style = browStroke)
            }
        }
        CharacterEmotion.SURPRISED -> {
            // 위로 올라간 눈썹
            val raisedY = browY - w * 0.025f
            for (sign in listOf(-1f, 1f)) {
                val path = Path().apply {
                    moveTo(cx + sign * (browX - w * 0.05f), raisedY + w * 0.012f)
                    quadraticTo(
                        cx + sign * browX, raisedY - w * 0.015f,
                        cx + sign * (browX + w * 0.05f), raisedY + w * 0.012f
                    )
                }
                drawPath(path, browColor, style = browStroke)
            }
        }
        else -> {
            // 기본 수평 호
            fun browPath(signX: Float) = Path().apply {
                moveTo(cx + signX * (browX - w * 0.05f), browY + w * 0.012f)
                quadraticTo(
                    cx + signX * browX, browY - w * 0.008f,
                    cx + signX * (browX + w * 0.05f), browY + w * 0.012f
                )
            }
            drawPath(browPath(-1f), browColor, style = browStroke)
            drawPath(browPath(+1f), browColor, style = browStroke)
        }
    }
}

// ── 속눈썹 라인 ─────────────────────────────────────────────

private fun DrawScope.drawEyelashes(cx: Float, faceCy: Float, faceR: Float, w: Float) {
    val eyeY = faceCy - faceR * 0.10f
    val eyeX = faceR * 0.38f
    val lashColor = Color(0xFF2A1810).copy(alpha = 0.6f)
    val lashStroke = Stroke(width = w * 0.014f, cap = StrokeCap.Round)

    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val path = Path().apply {
            moveTo(ex - w * 0.06f, eyeY - w * 0.06f)
            quadraticTo(ex, eyeY - w * 0.085f, ex + w * 0.06f, eyeY - w * 0.06f)
        }
        drawPath(path, lashColor, style = lashStroke)
    }
}

// ── 눈 ─────────────────────────────────────────────────────

private fun DrawScope.drawEyes(
    style: Int, cx: Float, faceCy: Float, faceR: Float, w: Float,
    emotion: CharacterEmotion, isBlinking: Boolean
) {
    val eyeY = faceCy - faceR * 0.10f
    val eyeX = faceR * 0.38f

    // 깜빡임 중이면 양쪽 다 감은 눈
    if (isBlinking && emotion != CharacterEmotion.HAPPY && emotion != CharacterEmotion.PLAYFUL) {
        for (sign in listOf(-1f, 1f)) {
            val ex = cx + sign * eyeX
            val path = Path().apply {
                moveTo(ex - w * 0.05f, eyeY)
                quadraticTo(ex, eyeY + w * 0.015f, ex + w * 0.05f, eyeY)
            }
            drawPath(path, Color(0xFF3B2A1A), style = Stroke(w * 0.022f, cap = StrokeCap.Round))
        }
        return
    }

    when (emotion) {
        CharacterEmotion.HAPPY -> drawHappyEyes(cx, eyeY, eyeX, w)
        CharacterEmotion.SHY -> drawShyEyes(cx, eyeY, eyeX, w, style)
        CharacterEmotion.SAD -> drawSadEyes(cx, eyeY, eyeX, w)
        CharacterEmotion.ANGRY -> drawAngryEyes(cx, eyeY, eyeX, w)
        CharacterEmotion.SURPRISED -> drawSurprisedEyes(cx, eyeY, eyeX, w)
        CharacterEmotion.LOVE -> drawLoveEyes(cx, eyeY, eyeX, w)
        CharacterEmotion.PLAYFUL -> drawPlayfulEyes(cx, eyeY, eyeX, w, style)
        CharacterEmotion.WORRIED -> drawWorriedEyes(cx, eyeY, eyeX, w, style)
        CharacterEmotion.TOUCHED -> drawTouchedEyes(cx, eyeY, eyeX, w)
        else -> drawNeutralEyes(cx, eyeY, eyeX, w, style)
    }
}

// NEUTRAL: 기존 스타일 기반으로 그리기 + 홍채 디테일
private fun DrawScope.drawNeutralEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float, style: Int) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        when (style) {
            0 -> drawAnimeEye(ex, eyeY, w, w * 0.055f, w * 0.065f, Color(0xFF3B2A1A))
            1 -> drawAnimeEye(ex, eyeY, w, w * 0.063f, w * 0.080f, Color(0xFF3B2A1A)) // 큰 눈
            2 -> { // 반달 눈
                val path = Path().apply {
                    moveTo(ex - w * 0.055f, eyeY)
                    quadraticTo(ex, eyeY - w * 0.06f, ex + w * 0.055f, eyeY)
                    quadraticTo(ex, eyeY + w * 0.022f, ex - w * 0.055f, eyeY)
                    close()
                }
                drawPath(path, Color(0xFF3B2A1A))
                drawCircle(Color.White, radius = w * 0.01f, center = Offset(ex + w * 0.012f, eyeY - w * 0.012f))
            }
            3 -> { // 별 눈
                drawOval(Color.White,
                    topLeft = Offset(ex - w * 0.058f, eyeY - w * 0.072f),
                    size    = Size(w * 0.116f, w * 0.144f))
                drawCircle(Color(0xFF6D28D9), radius = w * 0.042f, center = Offset(ex, eyeY))
                val starPath = Path().apply {
                    val r1 = w * 0.042f; val r2 = w * 0.016f
                    for (i in 0 until 8) {
                        val angle = (i * 45.0 - 90.0) * PI / 180.0
                        val r = if (i % 2 == 0) r1 else r2
                        val px = (ex + r * cos(angle)).toFloat()
                        val py = (eyeY + r * sin(angle)).toFloat()
                        if (i == 0) moveTo(px, py) else lineTo(px, py)
                    }
                    close()
                }
                drawPath(starPath, Color.White)
            }
            else -> drawAnimeEye(ex, eyeY, w, w * 0.055f, w * 0.065f, Color(0xFF3B2A1A))
        }
    }
}

// 애니메풍 눈 (홍채 2단계 + 하이라이트)
private fun DrawScope.drawAnimeEye(
    ex: Float, eyeY: Float, w: Float,
    halfW: Float, halfH: Float, irisColor: Color
) {
    // 흰자
    drawOval(Color.White,
        topLeft = Offset(ex - halfW, eyeY - halfH),
        size    = Size(halfW * 2, halfH * 2))
    // 홍채 외곽 (진한색)
    val outerIris = irisColor
    drawCircle(outerIris, radius = w * 0.042f, center = Offset(ex, eyeY))
    // 홍채 내부 (밝은색)
    val innerIris = Color(
        (irisColor.red * 1.3f).coerceAtMost(1f),
        (irisColor.green * 1.2f).coerceAtMost(1f),
        (irisColor.blue * 1.1f).coerceAtMost(1f),
        1f
    )
    drawCircle(innerIris, radius = w * 0.028f, center = Offset(ex, eyeY + w * 0.005f))
    // 동공
    drawCircle(Color.Black, radius = w * 0.020f, center = Offset(ex, eyeY))
    // 하이라이트 (큰)
    drawCircle(Color.White, radius = w * 0.013f, center = Offset(ex + w * 0.015f, eyeY - w * 0.018f))
    // 하이라이트 (작은)
    drawCircle(Color.White, radius = w * 0.007f, center = Offset(ex - w * 0.013f, eyeY + w * 0.015f))
}

// HAPPY: 반달 눈 (아래가 볼록한 호)
private fun DrawScope.drawHappyEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val path = Path().apply {
            moveTo(ex - w * 0.055f, eyeY - w * 0.01f)
            quadraticTo(ex, eyeY - w * 0.055f, ex + w * 0.055f, eyeY - w * 0.01f)
        }
        drawPath(path, Color(0xFF3B2A1A), style = Stroke(w * 0.024f, cap = StrokeCap.Round))
    }
}

// SHY: 시선 살짝 옆, 동공 작아짐
private fun DrawScope.drawShyEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float, style: Int) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.050f
        val halfH = w * 0.060f
        // 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH),
            size    = Size(halfW * 2, halfH * 2))
        // 시선 오프셋 (왼쪽 아래)
        val gazeX = ex - w * 0.012f
        val gazeY = eyeY + w * 0.008f
        drawCircle(Color(0xFF3B2A1A), radius = w * 0.030f, center = Offset(gazeX, gazeY))
        drawCircle(Color.Black, radius = w * 0.016f, center = Offset(gazeX, gazeY))
        drawCircle(Color.White, radius = w * 0.010f, center = Offset(gazeX + w * 0.010f, gazeY - w * 0.012f))
    }
}

// SAD: 눈 아래로 처짐 + 눈물
private fun DrawScope.drawSadEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.050f
        val halfH = w * 0.055f
        // 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH + w * 0.01f),
            size    = Size(halfW * 2, halfH * 2))
        // 홍채
        drawCircle(Color(0xFF3B2A1A), radius = w * 0.035f, center = Offset(ex, eyeY + w * 0.01f))
        drawCircle(Color.Black, radius = w * 0.020f, center = Offset(ex, eyeY + w * 0.01f))
        drawCircle(Color.White, radius = w * 0.010f, center = Offset(ex + w * 0.012f, eyeY - w * 0.008f))
        // 눈물 방울
        val tearDrop = Path().apply {
            val tx = ex + sign * w * 0.045f
            val ty = eyeY + w * 0.055f
            moveTo(tx, ty - w * 0.015f)
            quadraticTo(tx + w * 0.012f, ty + w * 0.010f, tx, ty + w * 0.020f)
            quadraticTo(tx - w * 0.012f, ty + w * 0.010f, tx, ty - w * 0.015f)
            close()
        }
        drawPath(tearDrop, Color(0xFF87CEEB).copy(alpha = 0.7f))
    }
}

// ANGRY: 찌푸린 눈
private fun DrawScope.drawAngryEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.048f
        val halfH = w * 0.050f
        // 흰자 (약간 좁아짐)
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH * 0.7f),
            size    = Size(halfW * 2, halfH * 1.4f))
        // 홍채 (빨간 기)
        drawCircle(Color(0xFF8B1A1A), radius = w * 0.033f, center = Offset(ex, eyeY))
        drawCircle(Color.Black, radius = w * 0.020f, center = Offset(ex, eyeY))
        drawCircle(Color.White, radius = w * 0.010f, center = Offset(ex + w * 0.012f, eyeY - w * 0.012f))
    }
}

// SURPRISED: 큰 눈 + 작은 동공 + 강한 하이라이트
private fun DrawScope.drawSurprisedEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.068f
        val halfH = w * 0.085f
        // 큰 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH),
            size    = Size(halfW * 2, halfH * 2))
        // 작은 동공
        drawCircle(Color(0xFF3B2A1A), radius = w * 0.028f, center = Offset(ex, eyeY))
        drawCircle(Color.Black, radius = w * 0.018f, center = Offset(ex, eyeY))
        // 강한 하이라이트
        drawCircle(Color.White, radius = w * 0.016f, center = Offset(ex + w * 0.018f, eyeY - w * 0.022f))
        drawCircle(Color.White, radius = w * 0.009f, center = Offset(ex - w * 0.015f, eyeY + w * 0.018f))
    }
}

// LOVE: 하트 동공
private fun DrawScope.drawLoveEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.060f
        val halfH = w * 0.072f
        // 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH),
            size    = Size(halfW * 2, halfH * 2))
        // 하트 동공
        val heartColor = Color(0xFFFF1493)
        val hs = w * 0.028f // heart size
        val heartPath = Path().apply {
            moveTo(ex, eyeY + hs * 0.7f)
            cubicTo(ex - hs * 1.2f, eyeY - hs * 0.2f, ex - hs * 0.6f, eyeY - hs * 1.0f, ex, eyeY - hs * 0.3f)
            cubicTo(ex + hs * 0.6f, eyeY - hs * 1.0f, ex + hs * 1.2f, eyeY - hs * 0.2f, ex, eyeY + hs * 0.7f)
            close()
        }
        drawPath(heartPath, heartColor)
        // 하이라이트
        drawCircle(Color.White.copy(alpha = 0.7f), radius = w * 0.008f, center = Offset(ex - w * 0.010f, eyeY - w * 0.015f))
    }
}

// PLAYFUL: 한쪽 윙크
private fun DrawScope.drawPlayfulEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float, style: Int) {
    // 왼쪽 눈: 정상
    val exLeft = cx - eyeX
    drawAnimeEye(exLeft, eyeY, w, w * 0.055f, w * 0.065f, Color(0xFF3B2A1A))

    // 오른쪽 눈: 윙크 (> 모양)
    val exRight = cx + eyeX
    val winkPath = Path().apply {
        moveTo(exRight - w * 0.04f, eyeY - w * 0.025f)
        lineTo(exRight + w * 0.01f, eyeY + w * 0.005f)
        lineTo(exRight - w * 0.04f, eyeY + w * 0.035f)
    }
    drawPath(winkPath, Color(0xFF3B2A1A), style = Stroke(w * 0.022f, cap = StrokeCap.Round))
}

// WORRIED: 눈 살짝 아래
private fun DrawScope.drawWorriedEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float, style: Int) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.052f
        val halfH = w * 0.060f
        // 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH + w * 0.008f),
            size    = Size(halfW * 2, halfH * 2))
        // 홍채 (살짝 아래)
        val gazeY = eyeY + w * 0.010f
        drawCircle(Color(0xFF3B2A1A), radius = w * 0.036f, center = Offset(ex, gazeY))
        drawCircle(Color.Black, radius = w * 0.020f, center = Offset(ex, gazeY))
        drawCircle(Color.White, radius = w * 0.011f, center = Offset(ex + w * 0.013f, gazeY - w * 0.015f))
    }
}

// TOUCHED: 반짝이는 큰 눈 + 눈물 반짝
private fun DrawScope.drawTouchedEyes(cx: Float, eyeY: Float, eyeX: Float, w: Float) {
    for (sign in listOf(-1f, 1f)) {
        val ex = cx + sign * eyeX
        val halfW = w * 0.063f
        val halfH = w * 0.078f
        // 큰 흰자
        drawOval(Color.White,
            topLeft = Offset(ex - halfW, eyeY - halfH),
            size    = Size(halfW * 2, halfH * 2))
        // 홍채 (밝은색)
        drawCircle(Color(0xFF5B3A1A), radius = w * 0.042f, center = Offset(ex, eyeY))
        drawCircle(Color(0xFF7B5A3A), radius = w * 0.030f, center = Offset(ex, eyeY + w * 0.004f))
        drawCircle(Color.Black, radius = w * 0.022f, center = Offset(ex, eyeY))
        // 큰 하이라이트 (반짝)
        drawCircle(Color.White, radius = w * 0.016f, center = Offset(ex + w * 0.016f, eyeY - w * 0.020f))
        drawCircle(Color.White, radius = w * 0.009f, center = Offset(ex - w * 0.014f, eyeY + w * 0.016f))
        // 눈물 반짝 (눈 아래)
        val sparkle = Color(0xFF87CEEB).copy(alpha = 0.5f)
        drawCircle(sparkle, radius = w * 0.006f, center = Offset(ex + sign * w * 0.05f, eyeY + w * 0.065f))
    }
}

// ── 코 ─────────────────────────────────────────────────────

private fun DrawScope.drawNose(cx: Float, faceCy: Float, faceR: Float, w: Float) {
    // 작은 'く' 형태 코
    val noseY = faceCy + faceR * 0.12f
    val nosePath = Path().apply {
        moveTo(cx + w * 0.005f, noseY - w * 0.015f)
        quadraticTo(cx - w * 0.012f, noseY + w * 0.005f, cx + w * 0.003f, noseY + w * 0.015f)
    }
    drawPath(nosePath, Color(0xFFD4A088).copy(alpha = 0.5f), style = Stroke(w * 0.012f, cap = StrokeCap.Round))
}

// ── 입 ─────────────────────────────────────────────────────

private fun DrawScope.drawMouth(
    cx: Float, faceCy: Float, faceR: Float, w: Float,
    emotion: CharacterEmotion
) {
    val my = faceCy + faceR * 0.38f
    val mouthColor = Color(0xFFE0607E)

    when (emotion) {
        CharacterEmotion.HAPPY -> {
            // 넓은 웃음 (입 벌림)
            val mouthPath = Path().apply {
                moveTo(cx - faceR * 0.28f, my - w * 0.008f)
                quadraticTo(cx, my + faceR * 0.25f, cx + faceR * 0.28f, my - w * 0.008f)
                quadraticTo(cx, my + faceR * 0.10f, cx - faceR * 0.28f, my - w * 0.008f)
                close()
            }
            drawPath(mouthPath, mouthColor)
            // 치아 하이라이트
            drawOval(Color.White,
                topLeft = Offset(cx - faceR * 0.10f, my),
                size = Size(faceR * 0.20f, faceR * 0.08f))
        }
        CharacterEmotion.SHY -> {
            // ω 입
            val path = Path().apply {
                moveTo(cx - faceR * 0.12f, my)
                quadraticTo(cx - faceR * 0.06f, my + faceR * 0.10f, cx, my + faceR * 0.03f)
                quadraticTo(cx + faceR * 0.06f, my + faceR * 0.10f, cx + faceR * 0.12f, my)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.022f, cap = StrokeCap.Round))
        }
        CharacterEmotion.SAD -> {
            // 아래로 처진 호
            val path = Path().apply {
                moveTo(cx - faceR * 0.18f, my + w * 0.008f)
                quadraticTo(cx, my - faceR * 0.10f, cx + faceR * 0.18f, my + w * 0.008f)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.024f, cap = StrokeCap.Round))
        }
        CharacterEmotion.ANGRY -> {
            // 꾹 다문 일자
            drawLine(mouthColor, Offset(cx - faceR * 0.18f, my), Offset(cx + faceR * 0.18f, my),
                strokeWidth = w * 0.028f)
            // 이빨 살짝
            val fangPath = Path().apply {
                moveTo(cx - faceR * 0.06f, my)
                lineTo(cx - faceR * 0.04f, my + w * 0.018f)
                lineTo(cx - faceR * 0.02f, my)
            }
            drawPath(fangPath, Color.White)
        }
        CharacterEmotion.SURPRISED -> {
            // 작은 O
            drawCircle(mouthColor.copy(alpha = 0.8f), radius = w * 0.035f, center = Offset(cx, my + w * 0.01f))
            drawCircle(Color(0xFF8B0000).copy(alpha = 0.3f), radius = w * 0.025f, center = Offset(cx, my + w * 0.01f))
        }
        CharacterEmotion.LOVE -> {
            // 하트 미소
            val path = Path().apply {
                moveTo(cx - faceR * 0.20f, my)
                quadraticTo(cx, my + faceR * 0.22f, cx + faceR * 0.20f, my)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.026f, cap = StrokeCap.Round))
        }
        CharacterEmotion.PLAYFUL -> {
            // 삐죽 웃음 (한쪽 올라감)
            val path = Path().apply {
                moveTo(cx - faceR * 0.16f, my + w * 0.005f)
                quadraticTo(cx, my + faceR * 0.14f, cx + faceR * 0.20f, my - w * 0.015f)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.024f, cap = StrokeCap.Round))
            // 혀
            val tonguePath = Path().apply {
                moveTo(cx + faceR * 0.02f, my + faceR * 0.08f)
                quadraticTo(cx + faceR * 0.08f, my + faceR * 0.16f, cx + faceR * 0.14f, my + faceR * 0.06f)
            }
            drawPath(tonguePath, Color(0xFFFF7B7B), style = Stroke(w * 0.020f, cap = StrokeCap.Round))
        }
        CharacterEmotion.WORRIED -> {
            // 물결 입
            val path = Path().apply {
                moveTo(cx - faceR * 0.15f, my + w * 0.005f)
                quadraticTo(cx - faceR * 0.07f, my - w * 0.012f, cx, my + w * 0.005f)
                quadraticTo(cx + faceR * 0.07f, my + w * 0.020f, cx + faceR * 0.15f, my + w * 0.005f)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.022f, cap = StrokeCap.Round))
        }
        CharacterEmotion.TOUCHED -> {
            // 작은 감동 웃음
            val path = Path().apply {
                moveTo(cx - faceR * 0.15f, my)
                quadraticTo(cx, my + faceR * 0.15f, cx + faceR * 0.15f, my)
            }
            drawPath(path, mouthColor, style = Stroke(w * 0.024f, cap = StrokeCap.Round))
        }
        else -> {
            // NEUTRAL: 작은 미소 (기존)
            val mouthPath = Path().apply {
                moveTo(cx - faceR * 0.22f, my)
                quadraticTo(cx, my + faceR * 0.18f, cx + faceR * 0.22f, my)
            }
            drawPath(mouthPath, mouthColor, style = Stroke(w * 0.026f, cap = StrokeCap.Round))
        }
    }
}

// ── 감정별 추가 이펙트 ──────────────────────────────────────

private fun DrawScope.drawEmotionEffects(
    emotion: CharacterEmotion, cx: Float, faceCy: Float, faceR: Float, w: Float
) {
    when (emotion) {
        CharacterEmotion.ANGRY -> {
            // 이마 위 화남 마크 (#)
            val mx = cx + faceR * 0.55f
            val my = faceCy - faceR * 0.65f
            val markColor = Color(0xFFFF4444)
            val markStroke = w * 0.012f
            drawLine(markColor, Offset(mx - w * 0.02f, my - w * 0.015f), Offset(mx + w * 0.02f, my - w * 0.015f), strokeWidth = markStroke)
            drawLine(markColor, Offset(mx - w * 0.02f, my + w * 0.005f), Offset(mx + w * 0.02f, my + w * 0.005f), strokeWidth = markStroke)
            drawLine(markColor, Offset(mx - w * 0.01f, my - w * 0.025f), Offset(mx - w * 0.01f, my + w * 0.015f), strokeWidth = markStroke)
            drawLine(markColor, Offset(mx + w * 0.01f, my - w * 0.025f), Offset(mx + w * 0.01f, my + w * 0.015f), strokeWidth = markStroke)
        }
        CharacterEmotion.SAD -> {
            // 머리 위 우울 구름
            val cloudColor = Color(0xFF8899AA).copy(alpha = 0.25f)
            drawCircle(cloudColor, radius = w * 0.035f, center = Offset(cx - w * 0.02f, faceCy - faceR * 0.85f))
            drawCircle(cloudColor, radius = w * 0.028f, center = Offset(cx + w * 0.03f, faceCy - faceR * 0.88f))
            drawCircle(cloudColor, radius = w * 0.030f, center = Offset(cx + w * 0.06f, faceCy - faceR * 0.82f))
        }
        else -> { /* no extra effects */ }
    }
}

// ── 악세서리 ───────────────────────────────────────────────

private fun DrawScope.drawAccessory(
    accessory: Int, hairColor: Color,
    cx: Float, cy: Float, faceCy: Float, faceR: Float, w: Float, h: Float
) {
    val topY = cy - h * 0.42f
    when (accessory) {
        1 -> { // 리본
            val rx = cx + w * 0.22f
            val ry = topY + h * 0.04f
            drawOval(hairColor, topLeft = Offset(rx - w * 0.11f, ry - h * 0.065f), size = Size(w * 0.09f, h * 0.13f))
            drawOval(hairColor, topLeft = Offset(rx + w * 0.02f, ry - h * 0.065f), size = Size(w * 0.09f, h * 0.13f))
            drawCircle(Color(0xFFFF69B4), radius = w * 0.030f, center = Offset(rx, ry))
        }
        2 -> { // 왕관
            val crownY   = topY - h * 0.01f
            val goldColor = Color(0xFFFFD700)
            val crownPath = Path().apply {
                moveTo(cx - w * 0.22f, crownY + h * 0.055f)
                lineTo(cx - w * 0.22f, crownY - h * 0.02f)
                lineTo(cx - w * 0.10f, crownY + h * 0.02f)
                lineTo(cx,             crownY - h * 0.07f)
                lineTo(cx + w * 0.10f, crownY + h * 0.02f)
                lineTo(cx + w * 0.22f, crownY - h * 0.02f)
                lineTo(cx + w * 0.22f, crownY + h * 0.055f)
                close()
            }
            drawPath(crownPath, goldColor)
            drawCircle(Color(0xFFFF0066), radius = w * 0.018f, center = Offset(cx,             crownY - h * 0.072f))
            drawCircle(Color(0xFF4169E1), radius = w * 0.013f, center = Offset(cx - w * 0.10f, crownY + h * 0.006f))
            drawCircle(Color(0xFF4169E1), radius = w * 0.013f, center = Offset(cx + w * 0.10f, crownY + h * 0.006f))
        }
        3 -> { // 안경
            val glassY    = faceCy - faceR * 0.10f
            val gColor    = Color(0xFF555555)
            val gStroke   = Stroke(w * 0.022f)
            drawRoundRect(gColor,
                topLeft = Offset(cx - w * 0.30f, glassY - h * 0.085f),
                size    = Size(w * 0.21f, h * 0.17f),
                cornerRadius = CornerRadius(w * 0.04f),
                style   = gStroke)
            drawRoundRect(gColor,
                topLeft = Offset(cx + w * 0.09f, glassY - h * 0.085f),
                size    = Size(w * 0.21f, h * 0.17f),
                cornerRadius = CornerRadius(w * 0.04f),
                style   = gStroke)
            drawLine(gColor, Offset(cx - w * 0.09f, glassY), Offset(cx + w * 0.09f, glassY), strokeWidth = w * 0.022f)
            drawLine(gColor, Offset(cx - w * 0.30f, glassY), Offset(cx - w * 0.43f, glassY - h * 0.01f), strokeWidth = w * 0.018f)
            drawLine(gColor, Offset(cx + w * 0.30f, glassY), Offset(cx + w * 0.43f, glassY - h * 0.01f), strokeWidth = w * 0.018f)
        }
        4 -> { // 고양이귀
            val earColor = hairColor
            val innerColor = Color(0xFFFFB5C2).copy(alpha = 0.6f)
            fun catEar(signX: Float) {
                val ex = cx + signX * w * 0.26f
                val outer = Path().apply {
                    moveTo(ex - signX * w * 0.02f, topY + h * 0.05f)
                    lineTo(ex + signX * w * 0.07f, topY - h * 0.07f)
                    lineTo(ex + signX * w * 0.15f, topY + h * 0.04f)
                    close()
                }
                val inner = Path().apply {
                    moveTo(ex - signX * w * 0.01f, topY + h * 0.03f)
                    lineTo(ex + signX * w * 0.06f, topY - h * 0.04f)
                    lineTo(ex + signX * w * 0.12f, topY + h * 0.03f)
                    close()
                }
                drawPath(outer, earColor)
                drawPath(inner, innerColor)
            }
            catEar(-1f)
            catEar(+1f)
        }
        5 -> { // 꽃 장식
            val flowerColors = listOf(Color(0xFFFF69B4), Color(0xFFFFD700), Color(0xFFFF6347))
            val positions = listOf(
                Offset(cx - w * 0.22f, topY + h * 0.04f),
                Offset(cx,             topY - h * 0.01f),
                Offset(cx + w * 0.22f, topY + h * 0.04f)
            )
            positions.forEachIndexed { i, pos ->
                val fc = flowerColors[i % flowerColors.size]
                for (angle in 0 until 360 step 72) {
                    val rad = angle.toDouble() * PI / 180.0
                    val px = (pos.x + w * 0.036f * cos(rad)).toFloat()
                    val py = (pos.y + w * 0.036f * sin(rad)).toFloat()
                    drawCircle(fc, radius = w * 0.028f, center = Offset(px, py))
                }
                drawCircle(Color(0xFFFFD700), radius = w * 0.020f, center = pos)
            }
        }
    }
}
