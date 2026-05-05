package com.example.mbtichatfriend.ui.diary

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel

// ── 32차/34차 스프린트: 주간 감정 리포트 화면 (Canvas 기반 막대 차트) ─────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiaryWeeklyReportScreen(
    viewModel: DiaryWeeklyReportViewModel = hiltViewModel(),
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("이번 주 감정 리포트") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
        ) {
            Spacer(Modifier.height(16.dp))

            Text(
                text = "이번 주 나의 감정",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "다이어리에 기록된 감정을 분석했어요",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(Modifier.height(24.dp))

            // 감정 5종 막대 차트 (Canvas 기반, 34차 고도화 포함)
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "감정 분포",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(16.dp))

                    val emotions = uiState.emotionCounts
                    val maxCount = emotions.values.maxOrNull()?.coerceAtLeast(1) ?: 1
                    val emotionColors = mapOf(
                        "\uD83D\uDE0A 기쁨" to Color(0xFFFDD835),
                        "\uD83D\uDE14 슬픔" to Color(0xFF42A5F5),
                        "\uD83D\uDE30 불안" to Color(0xFFAB47BC),
                        "\uD83D\uDE24 화남" to Color(0xFFEF5350),
                        "\uD83E\uDD14 복잡" to Color(0xFF78909C)
                    )

                    emotions.forEach { (emotion, count) ->
                        EmotionBarRow(
                            emotion = emotion,
                            count = count,
                            maxCount = maxCount,
                            barColor = emotionColors[emotion] ?: MaterialTheme.colorScheme.primary
                        )
                        Spacer(Modifier.height(12.dp))
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

            // 주간 요약 텍스트
            if (uiState.weeklySummary.isNotBlank()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.4f)
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "이번 주 한 줄 요약",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = uiState.weeklySummary,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            }

            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun EmotionBarRow(
    emotion: String,
    count: Int,
    maxCount: Int,
    barColor: Color
) {
    val ratio = count.toFloat() / maxCount.toFloat()

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = emotion,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.weight(0.35f),
            fontSize = 12.sp
        )

        // Canvas 기반 막대 차트
        Canvas(
            modifier = Modifier
                .weight(0.5f)
                .height(24.dp)
        ) {
            val barWidth = size.width * ratio
            drawRoundRect(
                color = barColor.copy(alpha = 0.25f),
                topLeft = Offset(0f, 0f),
                size = Size(size.width, size.height),
                cornerRadius = CornerRadius(8f)
            )
            if (barWidth > 0f) {
                drawRoundRect(
                    color = barColor,
                    topLeft = Offset(0f, 0f),
                    size = Size(barWidth, size.height),
                    cornerRadius = CornerRadius(8f)
                )
            }
        }

        Text(
            text = "${count}회",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.weight(0.15f),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 12.sp
        )
    }
}
