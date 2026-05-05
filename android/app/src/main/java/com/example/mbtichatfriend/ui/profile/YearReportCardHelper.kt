package com.example.mbtichatfriend.ui.profile

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.core.app.ShareCompat
import com.example.mbtichatfriend.data.remote.YearReportResponse

object YearReportCardHelper {

    private const val CARD_WIDTH = 1080
    private const val CARD_HEIGHT = 1920
    private const val DOWNLOAD_URL = "mbtichat.page.link/download"

    // 딥 퍼플 → 골드 그라데이션
    private const val COLOR_DEEP_PURPLE = 0xFF3D1F6E.toInt()
    private const val COLOR_GOLD = 0xFFD4AF37.toInt()

    fun createStoryCard(context: Context, report: YearReportResponse): Bitmap {
        val bitmap = Bitmap.createBitmap(CARD_WIDTH, CARD_HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경 그라데이션
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(
                0f, 0f,
                0f, CARD_HEIGHT.toFloat(),
                COLOR_DEEP_PURPLE,
                COLOR_GOLD,
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, 0f, CARD_WIDTH.toFloat(), CARD_HEIGHT.toFloat(), bgPaint)

        // ── 상단 영역 ──────────────────────────────────────
        // 앱 이름 로고 텍스트 (흰색, 48sp)
        val logoPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 48f * (context.resources.displayMetrics.density)
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        // sp → px 환경 독립적으로: 스토리 카드는 고정 크기이므로 density 무관하게 픽셀 직접 지정
        val logoPaintPx = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 72f   // ≈48sp at ~1.5x density (1080p 기준)
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("MBTIChatFriend", CARD_WIDTH / 2f, 200f, logoPaintPx)

        // 부제 텍스트 (흰색 70%, 36sp ≈ 54px)
        val subtitlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(179, 255, 255, 255) // 70% 불투명도
            textSize = 54f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("나의 2026 AI 친구 리포트", CARD_WIDTH / 2f, 290f, subtitlePaint)

        // 구분선
        val dividerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(100, 255, 255, 255)
            strokeWidth = 2f
        }
        canvas.drawLine(120f, 340f, CARD_WIDTH - 120f, 340f, dividerPaint)

        // ── 중앙 영역 ──────────────────────────────────────
        val centerY = CARD_HEIGHT / 2f

        // 총 대화 수 (흰색, 120sp ≈ 180px, bold)
        val countPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 180f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("${report.totalMessages}", CARD_WIDTH / 2f, centerY - 60f, countPaint)

        // "번의 대화" (흰색 70%, 48sp ≈ 72px)
        val countLabelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(179, 255, 255, 255)
            textSize = 72f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("번의 대화", CARD_WIDTH / 2f, centerY + 40f, countLabelPaint)

        // 가장 많이 대화한 MBTI — 골드 배경 흰글씨 배지
        report.topCharacter?.let { mbti ->
            val badgeTextPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.WHITE
                textSize = 60f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
                textAlign = Paint.Align.CENTER
            }
            val badgeLabelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.argb(179, 255, 255, 255)
                textSize = 44f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
                textAlign = Paint.Align.CENTER
            }
            val badgeBgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = COLOR_GOLD
            }

            val badgeText = "  $mbti  "
            val badgeWidth = badgeTextPaint.measureText(badgeText) + 80f
            val badgeHeight = 120f
            val badgeLeft = CARD_WIDTH / 2f - badgeWidth / 2f
            val badgeTop = centerY + 120f
            val badgeRight = CARD_WIDTH / 2f + badgeWidth / 2f
            val badgeBottom = badgeTop + badgeHeight

            canvas.drawRoundRect(
                RectF(badgeLeft, badgeTop, badgeRight, badgeBottom),
                24f, 24f, badgeBgPaint
            )
            canvas.drawText(mbti, CARD_WIDTH / 2f, badgeTop + 78f, badgeTextPaint)

            // 배지 위 라벨
            canvas.drawText("가장 많이 대화한 MBTI", CARD_WIDTH / 2f, badgeTop - 20f, badgeLabelPaint)
        }

        // ── 하단 영역 ──────────────────────────────────────
        // 가장 공감받은 고민 한 줄 (흰색, 이탤릭, 36sp ≈ 54px)
        report.topPostSummary?.let { summary ->
            val topPostPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.WHITE
                textSize = 54f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.ITALIC)
                textAlign = Paint.Align.CENTER
            }
            val topPostLabelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.argb(179, 255, 255, 255)
                textSize = 44f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
                textAlign = Paint.Align.CENTER
            }

            // 긴 텍스트 줄바꿈 처리
            val maxWidth = CARD_WIDTH - 200f
            val wrappedLines = wrapText(summary, maxWidth, topPostPaint)

            canvas.drawText("가장 공감받은 고민", CARD_WIDTH / 2f, CARD_HEIGHT - 380f, topPostLabelPaint)

            val lineSpacing = 64f
            val totalTextHeight = wrappedLines.size * lineSpacing
            var textY = CARD_HEIGHT - 320f
            for (line in wrappedLines.take(3)) {
                canvas.drawText(line, CARD_WIDTH / 2f, textY, topPostPaint)
                textY += lineSpacing
            }
        }

        // 구분선 (하단)
        canvas.drawLine(120f, CARD_HEIGHT - 160f, CARD_WIDTH - 120f, CARD_HEIGHT - 160f, dividerPaint)

        // 다운로드 URL (최하단, 흰색 소자, 28sp ≈ 42px)
        val urlPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(200, 255, 255, 255)
            textSize = 42f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(DOWNLOAD_URL, CARD_WIDTH / 2f, CARD_HEIGHT - 100f, urlPaint)

        return bitmap
    }

    fun shareStoryCard(bitmap: Bitmap, context: Context) {
        val uri = saveBitmapToMediaStore(bitmap, context) ?: return
        ShareCompat.IntentBuilder(context)
            .setType("image/png")
            .addStream(uri)
            .setChooserTitle("스토리 공유")
            .startChooser()
    }

    private fun saveBitmapToMediaStore(bitmap: Bitmap, context: Context): Uri? {
        return try {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, "mbtichat_story_${System.currentTimeMillis()}.png")
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

    private fun wrapText(text: String, maxWidth: Float, paint: Paint): List<String> {
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
        return lines
    }
}
