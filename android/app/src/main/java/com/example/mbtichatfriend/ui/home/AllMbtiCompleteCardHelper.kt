package com.example.mbtichatfriend.ui.home

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream

// ── 37차 스프린트: 16종 MBTI 전체 완성 공유 카드 헬퍼 ───────────────────────

object AllMbtiCompleteCardHelper {

    fun createAllCompleteCard(context: Context, userMbti: String): Bitmap {
        val width = 1080
        val height = 1920
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경: 무지개 그라데이션
        val gradient = LinearGradient(
            0f, 0f, width.toFloat(), height.toFloat(),
            intArrayOf(0xFF6C63FF.toInt(), 0xFFFF6584.toInt(), 0xFFFFD93D.toInt()),
            null,
            Shader.TileMode.CLAMP
        )
        canvas.drawPaint(Paint().apply { shader = gradient })

        // 중앙 제목 텍스트
        val paint = Paint().apply {
            color = Color.WHITE
            textSize = 72f
            textAlign = Paint.Align.CENTER
            isFakeBoldText = true
        }
        canvas.drawText("16가지 MBTI 친구 완성! \uD83C\uDF89", width / 2f, 400f, paint)

        // 사용자 MBTI 표시
        val userPaint = Paint().apply {
            color = Color.WHITE
            textSize = 52f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("$userMbti 유저의 완성 컬렉션", width / 2f, 500f, userPaint)

        // 16 MBTI 아이콘 그리드 (4×4)
        val mbtiList = listOf(
            "ENFP", "INFJ", "INTJ", "ISFJ",
            "INFP", "ENTP", "ESTJ", "ISFP",
            "INTP", "ESFP", "ENTJ", "ISTJ",
            "ESTP", "ENFJ", "ESFJ", "ISTP"
        )

        val cellW = width / 4f
        val cellH = 200f
        val startY = 600f

        mbtiList.forEachIndexed { i, mbti ->
            val x = (i % 4) * cellW + cellW / 2
            val y = startY + (i / 4) * cellH + 60f

            // 배경 원
            val circlePaint = Paint().apply {
                color = Color.WHITE
                alpha = 40
            }
            canvas.drawCircle(x, y - 20f, 60f, circlePaint)

            val smallPaint = Paint().apply {
                color = Color.WHITE
                textSize = 44f
                textAlign = Paint.Align.CENTER
                isFakeBoldText = true
            }
            canvas.drawText(mbti, x, y, smallPaint)
        }

        // 브랜드 워터마크
        val brandPaint = Paint().apply {
            color = Color.WHITE
            alpha = 180
            textSize = 44f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("MBTIChatFriend", width / 2f, 1800f, brandPaint)

        return bitmap
    }

    fun shareAllCompleteCard(bitmap: Bitmap, context: Context) {
        val file = File(context.cacheDir, "all_mbti_complete.png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(
                Intent.EXTRA_TEXT,
                "드디어 16가지 MBTI 친구를 모두 모았어요! \uD83C\uDF89 #MBTIChatFriend #MBTI완성"
            )
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "16종 완성 카드 공유하기"))
    }
}
