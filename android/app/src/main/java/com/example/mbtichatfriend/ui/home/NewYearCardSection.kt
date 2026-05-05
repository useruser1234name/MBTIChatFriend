package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// 홈 화면 상단에 1월 1일~10일 기간 동안만 노출 (LocalDate 비교)
// 날짜 조건: LocalDate.now().let { it.year == 2027 && it.monthValue == 1 && it.dayOfMonth <= 10 }

@Composable
fun NewYearCardSection(
    myMbti: String,
    onShare: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // 네이비 → 퍼플 그라데이션 배경
    val navyColor = Color(0xFF0A1628)
    val purpleColor = Color(0xFF6A0DAD)
    val goldColor = Color(0xFFD4AF37)

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(navyColor, purpleColor)
                )
            )
            .padding(20.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            // 제목
            Text(
                text = "2027년 새해 다짐 카드",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.ExtraBold,
                color = goldColor,
            )

            Spacer(Modifier.height(2.dp))

            // 다짐 문구
            Text(
                text = "내 MBTI(${myMbti})답게 2027년을 살겠습니다!",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White,
                lineHeight = 22.sp,
            )

            Spacer(Modifier.height(8.dp))

            // 공유하기 버튼
            Button(
                onClick = onShare,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = goldColor,
                    contentColor = navyColor,
                ),
            ) {
                Icon(
                    Icons.Default.Share,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = "공유하기",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                )
            }
        }
    }
}
