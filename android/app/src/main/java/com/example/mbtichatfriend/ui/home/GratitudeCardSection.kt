package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
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
import androidx.compose.material3.CircularProgressIndicator
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
import com.example.mbtichatfriend.ui.theme.GratitudeGold
import com.example.mbtichatfriend.ui.theme.GratitudeGoldDark
import com.example.mbtichatfriend.ui.theme.GratitudeOrange
import com.example.mbtichatfriend.ui.theme.GratitudeOrangeDark

// ── 가정의 달 감사 카드 섹션 (26차 스프린트) ─────────────────────────────────
// 날짜 조건: 4월 24일~5월 8일에만 노출
// (monthValue == 4 && dayOfMonth >= 24) || (monthValue == 5 && dayOfMonth <= 8)

@Composable
fun GratitudeCardSection(
    myMbti: String,
    isLoading: Boolean = false,
    onShare: () -> Unit,
    onStoryShare: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    // U2: 다크모드에서 라이트 전용 그라데이션이 그대로 밝게 워시되던 문제 —
    // 감정 버블과 동일한 isDark 분기 패턴 적용(hue 유지, 명도만 낮춘 Dark 대응색).
    val isDark = isSystemInDarkTheme()
    val orangeColor = if (isDark) GratitudeOrangeDark else GratitudeOrange
    val goldColor = if (isDark) GratitudeGoldDark else GratitudeGold
    val warmYellowColor = Color(0xFFFFF3E0)

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(orangeColor, goldColor)
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
                text = "💛 어버이날 감사 카드 만들기",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.ExtraBold,
                color = Color.White,
            )

            Spacer(Modifier.height(2.dp))

            // 부제 설명
            Text(
                text = "${myMbti.ifEmpty { "내" }} MBTI 맞춤 감사 메시지로\n특별한 카드를 만들어보세요!",
                style = MaterialTheme.typography.bodyMedium,
                color = warmYellowColor,
                lineHeight = 22.sp,
            )

            Spacer(Modifier.height(8.dp))

            // 일반 공유 버튼
            Button(
                onClick = onShare,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.White,
                    contentColor = orangeColor,
                ),
                enabled = !isLoading,
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = orangeColor,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            Icons.Default.Share,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "일반 공유",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                        )
                    }
                }
            }

            // 스토리 공유 버튼 (onStoryShare 제공 시에만 노출)
            if (onStoryShare != null) {
                Spacer(Modifier.height(6.dp))
                Button(
                    onClick = onStoryShare,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFFFFF8E1),
                        contentColor = Color(0xFFBF360C),
                    ),
                    enabled = !isLoading,
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            Icons.Default.Share,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "스토리 공유",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                        )
                    }
                }
            }
        }
    }
}
