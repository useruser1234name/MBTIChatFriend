package com.example.mbtichatfriend.ui.chat

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.core.app.ShareCompat
import com.example.mbtichatfriend.model.ChatMessage

object ShareMessageHelper {

    private const val WATERMARK_TEXT = "MBTIChatFriend · %s AI 친구와의 대화"
    private const val WATERMARK_URL = "mbtichat.page.link/share"
    private const val CANVAS_WIDTH = 1080
    private const val PADDING = 48f
    private const val BUBBLE_RADIUS = 24f
    private const val TEXT_SIZE_BODY = 36f
    private const val TEXT_SIZE_WATERMARK = 28f
    private const val LINE_SPACING = 16f
    private const val BUBBLE_PADDING_H = 32f
    private const val BUBBLE_PADDING_V = 20f
    private const val BUBBLE_MARGIN = 24f

    /**
     * 메시지 4개 기준 채팅 스냅샷 비트맵 생성
     * @param messages 캡처할 메시지 (최대 4개)
     * @param mbtiLabel MBTI 문자열 (워터마크용)
     */
    fun captureChatSnapshot(
        messages: List<ChatMessage>,
        mbtiLabel: String,
        context: Context,
    ): Bitmap {
        val bodyPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = TEXT_SIZE_BODY
            color = Color.BLACK
        }
        val watermarkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = TEXT_SIZE_WATERMARK
            color = Color.GRAY
        }
        val userBubblePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#E8F4FF")
        }
        val aiBubblePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#F5F5F5")
        }

        // 텍스트 줄바꿈 처리
        fun wrapText(text: String, maxWidth: Float, paint: Paint): List<String> {
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

        val maxBubbleWidth = CANVAS_WIDTH * 0.7f
        val maxTextWidth = maxBubbleWidth - BUBBLE_PADDING_H * 2

        // 각 메시지 높이 계산
        data class RenderedMessage(
            val message: ChatMessage,
            val lines: List<String>,
            val bubbleHeight: Float,
            val isUser: Boolean,
        )

        val rendered = messages.map { msg ->
            val isUser = msg.isFromUser
            val lines = wrapText(msg.text, maxTextWidth, bodyPaint)
            val bubbleHeight = lines.size * (TEXT_SIZE_BODY + LINE_SPACING) + BUBBLE_PADDING_V * 2
            RenderedMessage(msg, lines, bubbleHeight, isUser)
        }

        // 캔버스 총 높이 계산 (워터마크 텍스트 + URL 텍스트 줄 포함)
        val urlTextSize = TEXT_SIZE_WATERMARK - 4f
        val watermarkHeight = TEXT_SIZE_WATERMARK + urlTextSize + 4f + PADDING * 2
        val totalHeight = rendered.sumOf { (it.bubbleHeight + BUBBLE_MARGIN).toDouble() }.toFloat() +
                PADDING * 2 + watermarkHeight

        val bitmap = Bitmap.createBitmap(CANVAS_WIDTH, totalHeight.toInt().coerceAtLeast(400), Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        canvas.drawColor(Color.WHITE)

        var y = PADDING
        for (rm in rendered) {
            val bubblePaint = if (rm.isUser) userBubblePaint else aiBubblePaint
            val bubbleLeft = if (rm.isUser) CANVAS_WIDTH - maxBubbleWidth - PADDING else PADDING
            val bubbleRight = if (rm.isUser) CANVAS_WIDTH - PADDING.toFloat() else PADDING + maxBubbleWidth

            // 말풍선
            val rect = RectF(bubbleLeft, y, bubbleRight, y + rm.bubbleHeight)
            canvas.drawRoundRect(rect, BUBBLE_RADIUS, BUBBLE_RADIUS, bubblePaint)

            // 텍스트
            var textY = y + BUBBLE_PADDING_V + TEXT_SIZE_BODY
            for (line in rm.lines) {
                val textX = if (rm.isUser) bubbleRight - BUBBLE_PADDING_H - bodyPaint.measureText(line)
                            else bubbleLeft + BUBBLE_PADDING_H
                canvas.drawText(line, textX, textY, bodyPaint)
                textY += TEXT_SIZE_BODY + LINE_SPACING
            }

            y += rm.bubbleHeight + BUBBLE_MARGIN
        }

        // 워터마크
        val watermarkText = WATERMARK_TEXT.format(mbtiLabel)
        val watermarkX = (CANVAS_WIDTH - watermarkPaint.measureText(watermarkText)) / 2f
        val watermarkY = y + PADDING + TEXT_SIZE_WATERMARK
        canvas.drawText(watermarkText, watermarkX, watermarkY, watermarkPaint)

        // 딥링크 URL
        val urlPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = TEXT_SIZE_WATERMARK - 4f  // 약간 작게
            color = Color.parseColor("#0066CC")  // 링크 색상
        }
        val urlX = (CANVAS_WIDTH - urlPaint.measureText(WATERMARK_URL)) / 2f
        canvas.drawText(WATERMARK_URL, urlX, watermarkY + TEXT_SIZE_WATERMARK + 4f, urlPaint)

        return bitmap
    }

    /**
     * 비트맵을 MediaStore에 저장 후 공유 시트 표시
     */
    fun shareSnapshot(bitmap: Bitmap, context: Context) {
        val uri = saveBitmapToMediaStore(bitmap, context) ?: return
        ShareCompat.IntentBuilder(context)
            .setType("image/png")
            .addStream(uri)
            .setChooserTitle("대화 공유")
            .startChooser()
    }

    private fun saveBitmapToMediaStore(bitmap: Bitmap, context: Context): Uri? {
        return try {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, "mbtichat_${System.currentTimeMillis()}.png")
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
