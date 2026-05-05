package com.example.mbtichatfriend.ui.home

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.core.app.ShareCompat

// ── 가정의 달 감사 카드 (26차 스프린트) ──────────────────────────────────────

object GratitudeCardHelper {

    private const val CARD_WIDTH = 1080
    private const val CARD_HEIGHT = 1920
    private const val WATERMARK = "MBTIChatFriend · mbtichat.page.link/download"

    // 따뜻한 오렌지 → 골드 그라데이션
    private const val COLOR_ORANGE = 0xFFE8621A.toInt()
    private const val COLOR_GOLD = 0xFFD4AF37.toInt()

    fun createGratitudeCard(context: Context, mbti: String, message: String): Bitmap {
        val bitmap = Bitmap.createBitmap(CARD_WIDTH, CARD_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경 그라데이션 (오렌지 → 골드)
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(
                0f, 0f,
                CARD_WIDTH.toFloat(), CARD_HEIGHT.toFloat(),
                COLOR_ORANGE,
                COLOR_GOLD,
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, 0f, CARD_WIDTH.toFloat(), CARD_HEIGHT.toFloat(), bgPaint)

        // 상단 로고: "MBTIChatFriend"
        val logoPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 72f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("MBTIChatFriend", CARD_WIDTH / 2f, 200f, logoPaint)

        // 장식선 (상단)
        val decorPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(180, 255, 255, 255)
            strokeWidth = 3f
        }
        canvas.drawLine(160f, 250f, CARD_WIDTH - 160f, 250f, decorPaint)

        // MBTI 배지 배경 (흰색 반투명 원형 배지)
        val badgeCenterX = CARD_WIDTH / 2f
        val badgeCenterY = 700f
        val badgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(60, 255, 255, 255)
        }
        canvas.drawCircle(badgeCenterX, badgeCenterY, 200f, badgePaint)

        // MBTI 텍스트 (배지 중앙)
        val mbtiPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 120f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(mbti, badgeCenterX, badgeCenterY + 42f, mbtiPaint)

        // 장식선 (중앙 위)
        canvas.drawLine(200f, 960f, CARD_WIDTH - 200f, 960f, decorPaint)

        // 감사 메시지 텍스트 (줄 바꿈 처리)
        val msgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 56f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        drawMultilineText(canvas, message, msgPaint, CARD_WIDTH / 2f, 1060f, CARD_WIDTH - 160f, 80f)

        // 장식선 (중앙 아래)
        canvas.drawLine(200f, 1580f, CARD_WIDTH - 200f, 1580f, decorPaint)

        // 하단 문구: "어버이날 감사합니다"
        val bottomPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 88f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("어버이날 감사합니다", CARD_WIDTH / 2f, 1700f, bottomPaint)

        // 하트 장식
        val heartPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(200, 255, 200, 100)
            textSize = 72f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("💛", CARD_WIDTH / 2f, 1800f, heartPaint)

        // 워터마크
        val watermarkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(140, 255, 255, 255)
            textSize = 38f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(WATERMARK, CARD_WIDTH / 2f, CARD_HEIGHT - 80f, watermarkPaint)

        return bitmap
    }

    /**
     * 인스타그램 스토리 최적화 세로형 카드 (28차 스프린트)
     * - 1080×1920, 오렌지→골드 세로 방향 그라데이션 (더 강조)
     * - 상단 여백 더 크게, 중앙 MBTI 배지 더 크게 (280px)
     * - 하단: "mbtichat.page.link/download" + QR 코드 텍스트
     */
    fun createInstagramStoryCard(context: Context, mbti: String, message: String): Bitmap {
        val bitmap = Bitmap.createBitmap(CARD_WIDTH, CARD_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경 그라데이션: 오렌지→골드 세로 방향으로 더 강조 (상→하)
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(
                0f, 0f,
                0f, CARD_HEIGHT.toFloat(),
                intArrayOf(COLOR_ORANGE, COLOR_GOLD, COLOR_ORANGE),
                floatArrayOf(0f, 0.55f, 1f),
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, 0f, CARD_WIDTH.toFloat(), CARD_HEIGHT.toFloat(), bgPaint)

        // 상단 여백 더 크게: 로고를 아래로 내림 (기존 200 → 280)
        val logoPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 72f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("MBTIChatFriend", CARD_WIDTH / 2f, 300f, logoPaint)

        // 장식선 (로고 아래)
        val decorPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(180, 255, 255, 255)
            strokeWidth = 3f
        }
        canvas.drawLine(160f, 360f, CARD_WIDTH - 160f, 360f, decorPaint)

        // MBTI 배지: 더 크게 (280px, 기존 200px)
        val badgeCenterX = CARD_WIDTH / 2f
        val badgeCenterY = 820f
        val badgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(70, 255, 255, 255)
        }
        canvas.drawCircle(badgeCenterX, badgeCenterY, 280f, badgePaint)

        // MBTI 텍스트 (배지 중앙, 더 크게)
        val mbtiPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 148f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(mbti, badgeCenterX, badgeCenterY + 52f, mbtiPaint)

        // 장식선 (배지 아래)
        canvas.drawLine(200f, 1170f, CARD_WIDTH - 200f, 1170f, decorPaint)

        // 감사 메시지 텍스트
        val msgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 56f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        drawMultilineText(canvas, message, msgPaint, CARD_WIDTH / 2f, 1270f, CARD_WIDTH - 160f, 80f)

        // 장식선 (메시지 아래)
        canvas.drawLine(200f, 1630f, CARD_WIDTH - 200f, 1630f, decorPaint)

        // 하단 문구: "어버이날 감사합니다"
        val bottomPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 80f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("어버이날 감사합니다", CARD_WIDTH / 2f, 1720f, bottomPaint)

        // 하트 장식
        val heartPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(200, 255, 200, 100)
            textSize = 64f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("💛", CARD_WIDTH / 2f, 1800f, heartPaint)

        // 하단 다운로드 링크 + QR 안내
        val linkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(200, 255, 255, 255)
            textSize = 42f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("mbtichat.page.link/download", CARD_WIDTH / 2f, CARD_HEIGHT - 120f, linkPaint)

        val qrHintPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(150, 255, 255, 255)
            textSize = 34f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("▲ QR로 앱 다운로드", CARD_WIDTH / 2f, CARD_HEIGHT - 60f, qrHintPaint)

        return bitmap
    }

    fun shareInstagramStoryCard(bitmap: Bitmap, context: Context) {
        val uri = saveBitmapToMediaStore(bitmap, context) ?: return
        ShareCompat.IntentBuilder(context)
            .setType("image/png")
            .addStream(uri)
            .setChooserTitle("어버이날 스토리 카드 공유")
            .startChooser()
    }

    /**
     * 긴 메시지를 maxWidth에 맞춰 줄 바꿈하여 그립니다.
     */
    private fun drawMultilineText(
        canvas: Canvas,
        text: String,
        paint: Paint,
        x: Float,
        startY: Float,
        maxWidth: Float,
        lineHeight: Float,
    ) {
        val words = text.split(" ")
        val lines = mutableListOf<String>()
        var currentLine = ""

        for (word in words) {
            val testLine = if (currentLine.isEmpty()) word else "$currentLine $word"
            if (paint.measureText(testLine) <= maxWidth) {
                currentLine = testLine
            } else {
                if (currentLine.isNotEmpty()) lines.add(currentLine)
                currentLine = word
            }
        }
        if (currentLine.isNotEmpty()) lines.add(currentLine)

        // 최대 8줄까지만 출력
        val maxLines = 8
        val drawLines = lines.take(maxLines)
        var y = startY
        for (line in drawLines) {
            canvas.drawText(line, x, y, paint)
            y += lineHeight
        }
    }

    fun shareGratitudeCard(bitmap: Bitmap, context: Context) {
        val uri = saveBitmapToMediaStore(bitmap, context) ?: return
        ShareCompat.IntentBuilder(context)
            .setType("image/png")
            .addStream(uri)
            .setChooserTitle("어버이날 감사 카드 공유")
            .startChooser()
    }

    private fun saveBitmapToMediaStore(bitmap: Bitmap, context: Context): Uri? {
        return try {
            val values = ContentValues().apply {
                put(
                    MediaStore.Images.Media.DISPLAY_NAME,
                    "mbtichat_gratitude_${System.currentTimeMillis()}.png"
                )
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }
            }
            val uri = context.contentResolver.insert(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values
            ) ?: return null

            context.contentResolver.openOutputStream(uri)?.use {
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                values.clear()
                values.put(MediaStore.Images.Media.IS_PENDING, 0)
                context.contentResolver.update(uri, values, null, null)
            }
            uri
        } catch (e: Exception) {
            null
        }
    }
}
