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

object NewYearCardHelper {

    private const val CARD_SIZE = 1080
    private const val WATERMARK = "MBTIChatFriend · mbtichat.page.link/download"

    // 네이비 → 퍼플 그라데이션
    private const val COLOR_NAVY = 0xFF0A1628.toInt()
    private const val COLOR_PURPLE = 0xFF6A0DAD.toInt()

    fun createNewYearCard(context: Context, myMbti: String): Bitmap {
        val bitmap = Bitmap.createBitmap(CARD_SIZE, CARD_SIZE, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        // 배경 그라데이션 (네이비 → 퍼플)
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(
                0f, 0f,
                CARD_SIZE.toFloat(), CARD_SIZE.toFloat(),
                COLOR_NAVY,
                COLOR_PURPLE,
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, 0f, CARD_SIZE.toFloat(), CARD_SIZE.toFloat(), bgPaint)

        // "2027" 대형 텍스트 (흰색, bold, 220px)
        val yearPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 220f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("2027", CARD_SIZE / 2f, 350f, yearPaint)

        // "새해 복 많이 받으세요" 부제 (반투명 흰색, 60px)
        val subtitlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(200, 255, 255, 255)
            textSize = 60f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("새해 복 많이 받으세요", CARD_SIZE / 2f, 440f, subtitlePaint)

        // 구분 장식선
        val decorPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(150, 212, 175, 55) // 골드 계열
            strokeWidth = 3f
        }
        canvas.drawLine(200f, 490f, CARD_SIZE - 200f, 490f, decorPaint)

        // "${myMbti}답게" 텍스트 (골드 계열 + 흰색, bold, 96px)
        val mbtiBoldPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#D4AF37") // 골드
            textSize = 96f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("${myMbti}답게", CARD_SIZE / 2f, 620f, mbtiBoldPaint)

        // 다짐 문구 (흰색, 70px)
        val resolutionPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 70f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("2027년을 살겠습니다!", CARD_SIZE / 2f, 730f, resolutionPaint)

        // 장식선 (하단)
        canvas.drawLine(200f, 790f, CARD_SIZE - 200f, 790f, decorPaint)

        // 앱 이름 워터마크 (흰색 반투명, 42px)
        val watermarkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(160, 255, 255, 255)
            textSize = 42f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(WATERMARK, CARD_SIZE / 2f, CARD_SIZE - 80f, watermarkPaint)

        return bitmap
    }

    fun shareNewYearCard(bitmap: Bitmap, context: Context) {
        val uri = saveBitmapToMediaStore(bitmap, context) ?: return
        ShareCompat.IntentBuilder(context)
            .setType("image/png")
            .addStream(uri)
            .setChooserTitle("새해 다짐 카드 공유")
            .startChooser()
    }

    private fun saveBitmapToMediaStore(bitmap: Bitmap, context: Context): Uri? {
        return try {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, "mbtichat_newyear_${System.currentTimeMillis()}.png")
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
