package com.example.mbtichatfriend.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

// ── 가정의 달 사전 홍보 배너 (28차 스프린트) ─────────────────────────────────
// 날짜 조건: 2027년 4월 10일~23일 기간에만 노출
// 클릭 시 Snackbar: "4월 24일 공개됩니다 💕"

@Composable
fun GratitudeTeaserCard(
    visible: Boolean,
    snackbarHostState: SnackbarHostState,
    modifier: Modifier = Modifier,
) {
    val coroutineScope = rememberCoroutineScope()

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = modifier,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 0.dp, vertical = 4.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(Color(0xFFFFF3E0))
                .clickable {
                    coroutineScope.launch {
                        snackbarHostState.showSnackbar("4월 24일 공개됩니다 💕")
                    }
                }
                .padding(16.dp)
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = "💛 곧 어버이날이에요!",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFBF360C),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "MBTI별 감사 카드를 준비해보세요.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF6D4C41),
                    lineHeight = 20.sp,
                )
            }
        }
    }
}
