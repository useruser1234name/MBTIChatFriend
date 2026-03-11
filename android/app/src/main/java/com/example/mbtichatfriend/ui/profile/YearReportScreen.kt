package com.example.mbtichatfriend.ui.profile

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.mbtichatfriend.data.remote.YearReportResponse

// 연말 느낌 그라데이션 색상: 딥 퍼플 → 골드
private val GradientStart = Color(0xFF4A148C)
private val GradientEnd = Color(0xFFFFD54F)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YearReportScreen(
    onNavigateBack: () -> Unit,
    viewModel: YearReportViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("2026 나의 대화 리포트", color = Color.White) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = GradientStart,
                ),
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(
                    Brush.verticalGradient(listOf(GradientStart, GradientEnd))
                )
        ) {
            when (val state = uiState) {
                is YearReportUiState.Loading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Color.White)
                    }
                }

                is YearReportUiState.Error -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            state.message,
                            color = Color.White,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(24.dp)
                        )
                    }
                }

                is YearReportUiState.Success -> {
                    YearReportContent(
                        report = state.report,
                        onShare = {
                            val shareText = buildString {
                                appendLine("[ 2026 나의 대화 리포트 ]")
                                appendLine()
                                appendLine("총 대화 수: ${state.report.totalMessages}개")
                                state.report.topCharacter?.let {
                                    appendLine("가장 많이 대화한 MBTI: $it")
                                }
                                state.report.topPostSummary?.let {
                                    appendLine("가장 공감받은 고민: $it (공감 ${state.report.topPostEmpathy}개)")
                                }
                                appendLine()
                                append("MBTIChatFriend에서 나의 대화 리포트 확인!")
                            }
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                putExtra(Intent.EXTRA_TEXT, shareText)
                                type = "text/plain"
                            }
                            context.startActivity(Intent.createChooser(intent, "리포트 공유"))
                        },
                        onStoryShare = {
                            val bitmap = YearReportCardHelper.createStoryCard(context, state.report)
                            YearReportCardHelper.shareStoryCard(bitmap, context)
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun YearReportContent(
    report: YearReportResponse,
    onShare: () -> Unit,
    onStoryShare: () -> Unit = {},
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Spacer(Modifier.height(8.dp))

        // 헤더
        Text(
            text = "2026",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.ExtraBold,
            color = GradientEnd,
        )
        Text(
            text = "나의 대화 리포트",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(4.dp))

        // 총 대화 수
        ReportCard(
            label = "총 대화 수",
            value = "${report.totalMessages}개",
            emoji = "💬",
        )

        // 가장 많이 대화한 MBTI
        report.topCharacter?.let { mbti ->
            ReportCard(
                label = "가장 많이 대화한 MBTI",
                value = mbti,
                emoji = "🤝",
            )
        }

        // 가장 공감받은 고민
        report.topPostSummary?.let { summary ->
            ReportCard(
                label = "가장 공감받은 고민",
                value = "$summary\n(공감 ${report.topPostEmpathy}개)",
                emoji = "🌟",
            )
        }

        Spacer(Modifier.height(8.dp))

        // 공유 버튼
        Button(
            onClick = onShare,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = GradientEnd,
                contentColor = GradientStart,
            ),
        ) {
            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(20.dp))
            Text(
                text = "  리포트 공유하기",
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
            )
        }

        // 스토리 공유 버튼 (1080×1920 인스타 카드)
        OutlinedButton(
            onClick = onStoryShare,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = Color.White,
            ),
            border = androidx.compose.foundation.BorderStroke(1.5.dp, GradientEnd),
        ) {
            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(20.dp))
            Text(
                text = "  스토리 공유",
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
            )
        }

        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun ReportCard(
    label: String,
    value: String,
    emoji: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color.White.copy(alpha = 0.15f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = emoji,
                fontSize = 32.sp,
            )
            Column {
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelMedium,
                    color = Color.White.copy(alpha = 0.75f),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = value,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
            }
        }
    }
}
