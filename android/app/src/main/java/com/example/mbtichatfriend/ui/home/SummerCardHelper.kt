package com.example.mbtichatfriend.ui.home

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream

// ── 34차 스프린트: 여름 바이럴 카드 생성 헬퍼 ────────────────────────────────

object SummerCardHelper {

    fun createSummerCard(context: Context, mbti: String): Bitmap {
        val width = 1080
        val height = 1080
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경: 하늘색 → 노란색 그라데이션
        val gradient = LinearGradient(
            0f, 0f, 0f, height.toFloat(),
            intArrayOf(0xFF29B6F6.toInt(), 0xFFFFF176.toInt()),
            null,
            Shader.TileMode.CLAMP
        )
        val bgPaint = Paint().apply { shader = gradient }
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), bgPaint)

        // 중앙 텍스트
        val titlePaint = Paint().apply {
            color = android.graphics.Color.WHITE
            textSize = 96f
            textAlign = Paint.Align.CENTER
            isFakeBoldText = true
        }
        canvas.drawText("☀️ 여름 MBTI 카드", width / 2f, 300f, titlePaint)

        val mbtiPaint = Paint().apply {
            color = android.graphics.Color.WHITE
            textSize = 128f
            textAlign = Paint.Align.CENTER
            isFakeBoldText = true
        }
        canvas.drawText(mbti, width / 2f, 500f, mbtiPaint)

        val subPaint = Paint().apply {
            color = android.graphics.Color.WHITE
            textSize = 64f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("친구와 함께하는 여름!", width / 2f, 620f, subPaint)

        val brandPaint = Paint().apply {
            color = android.graphics.Color.WHITE.and(0xAAFFFFFF.toInt())
            textSize = 44f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("MBTIChatFriend", width / 2f, 900f, brandPaint)

        return bitmap
    }

    fun shareSummerCard(bitmap: Bitmap, context: Context) {
        val file = File(context.cacheDir, "summer_card.png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_TEXT, "MBTIChatFriend와 함께하는 여름! ☀️ #MBTIChatFriend #여름MBTI")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "여름 카드 공유하기"))
    }
}
