package com.example.mbtichatfriend.ui.home

import android.graphics.Bitmap
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.LocalDate

// ── 34차 스프린트: 여름 MBTI 바이럴 카드 섹션 (6~8월) ────────────────────────

@Composable
fun SummerCardSection(
    mbti: String,
    onShare: (Bitmap) -> Unit,
    modifier: Modifier = Modifier
) {
    val show = LocalDate.now().monthValue in 6..8
    if (!show) return

    val context = LocalContext.current

    Card(
        modifier = modifier.fillMaxWidth().padding(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF176))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "\u2600\uFE0F 여름 MBTI 카드",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "$mbti 친구와 함께하는 여름!",
                style = MaterialTheme.typography.bodyMedium
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    val bitmap = SummerCardHelper.createSummerCard(context, mbti)
                    onShare(bitmap)
                }
            ) {
                Text("카드 만들기")
            }
        }
    }
}
