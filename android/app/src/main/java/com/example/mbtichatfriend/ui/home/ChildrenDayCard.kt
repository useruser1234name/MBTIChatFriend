package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.LocalDate

// ── 31차 스프린트: 어린이날 시즌 카드 (2027-05-01 ~ 2027-05-05) ──────────────

@Composable
fun ChildrenDayCard(onDismiss: () -> Unit) {
    val show = LocalDate.now().let { it.monthValue == 5 && it.dayOfMonth in 1..5 && it.year == 2027 }
    if (!show) return

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(
                Brush.horizontalGradient(
                    listOf(Color(0xFFFFB74D), Color(0xFFFF7043))
                )
            )
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                text = "\uD83C\uDF88 어린이날이에요!",
                style = MaterialTheme.typography.titleMedium,
                color = Color.White,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "MBTI 친구와 특별한 하루 보내요!",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.9f)
            )
            TextButton(onClick = onDismiss) {
                Text("확인", color = Color.White)
            }
        }
    }
}
