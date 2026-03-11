package com.example.mbtichatfriend.ui.compatibility

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import java.time.LocalDate

// 2027년 2월 1일~14일을 발렌타인 시즌으로 간주 (24차 스프린트)
private val isValentineSeason: Boolean
    get() = LocalDate.now().let { it.year == 2027 && it.monthValue == 2 && it.dayOfMonth <= 14 }

private val valentineGradient = Brush.verticalGradient(
    colors = listOf(Color(0xFFFFB6C1), Color(0xFFFF69B4)),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompatibilityScreen(
    myMbti: String,
    characterMbti: String,
    onNavigateBack: () -> Unit,
    viewModel: CompatibilityViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val valentineSeason = isValentineSeason

    LaunchedEffect(myMbti, characterMbti) {
        viewModel.loadCompatibility(myMbti, characterMbti)
    }

    // 발렌타인 시즌이고 궁합 로드 완료 시 메시지도 요청
    LaunchedEffect(uiState) {
        if (valentineSeason && uiState is CompatibilityUiState.Success &&
            (uiState as CompatibilityUiState.Success).valentineMessage == null
        ) {
            viewModel.loadValentineMessage(myMbti)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (valentineSeason) "💕 발렌타인 궁합" else "우리의 궁합") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로")
                    }
                },
                actions = {
                    if (uiState is CompatibilityUiState.Success) {
                        IconButton(onClick = {
                            val state = uiState as CompatibilityUiState.Success
                            val shareUrl = "https://mbtichat.page.link/compat?a=${myMbti}&b=${characterMbti}&utm_source=compatibility&utm_medium=share"
                            val shareText = "나(${myMbti})와 ${characterMbti}의 궁합은 '${state.result.type}'!\n${shareUrl}"
                            val sendIntent = android.content.Intent().apply {
                                action = android.content.Intent.ACTION_SEND
                                putExtra(android.content.Intent.EXTRA_TEXT, shareText)
                                type = "text/plain"
                            }
                            context.startActivity(android.content.Intent.createChooser(sendIntent, "궁합 공유"))
                        }) {
                            Icon(Icons.Default.Share, "공유")
                        }
                    }
                }
            )
        }
    ) { padding ->
        when (val state = uiState) {
            is CompatibilityUiState.Loading -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            is CompatibilityUiState.Success -> {
                val backgroundModifier = if (valentineSeason) {
                    Modifier
                        .padding(padding)
                        .fillMaxSize()
                        .background(brush = valentineGradient)
                } else {
                    Modifier
                        .padding(padding)
                        .fillMaxSize()
                }

                Column(
                    modifier = backgroundModifier
                        .verticalScroll(rememberScrollState())
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    // 발렌타인 배너 (시즌 전용)
                    if (valentineSeason) {
                        ValentineBanner()
                    }

                    // MBTI 조합 표시
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        MbtiChip(myMbti, valentine = valentineSeason)
                        Text(
                            if (valentineSeason) "♥" else "×",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Light,
                            color = if (valentineSeason) Color(0xFFFF1493) else MaterialTheme.colorScheme.onSurface,
                        )
                        MbtiChip(characterMbti, valentine = valentineSeason)
                    }

                    // 궁합 유형 배지
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = if (valentineSeason) Color(0xFFFF1493) else MaterialTheme.colorScheme.primaryContainer,
                    ) {
                        Text(
                            state.result.type,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                            style = MaterialTheme.typography.labelLarge,
                            color = if (valentineSeason) Color.White else MaterialTheme.colorScheme.onPrimaryContainer,
                            fontWeight = FontWeight.Bold,
                        )
                    }

                    // 제목 + 설명
                    Text(
                        state.result.title,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                    )
                    Text(
                        state.result.description,
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    // 대화 팁
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            Text(
                                "대화 팁",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                            )
                            Spacer(Modifier.height(12.dp))
                            state.result.tips.forEach { tip ->
                                Row(
                                    modifier = Modifier.padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    Text("•", color = MaterialTheme.colorScheme.primary)
                                    Text(tip, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }

                    // 나에게 보내는 발렌타인 메시지 카드 (시즌 전용)
                    if (valentineSeason && state.valentineMessage != null) {
                        ValentineMessageCard(message = state.valentineMessage.message)
                    }
                }
            }
            is CompatibilityUiState.Error -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    Text(state.message)
                }
            }
        }
    }
}

@Composable
private fun ValentineBanner() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFFFF69B4).copy(alpha = 0.25f),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.Favorite,
                contentDescription = null,
                tint = Color(0xFFFF1493),
            )
            Text(
                "💕 발렌타인 특집 궁합",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = Color(0xFFFF1493),
            )
        }
    }
}

@Composable
private fun ValentineMessageCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFFFF0F5),
        ),
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.Favorite,
                    contentDescription = null,
                    tint = Color(0xFFFF69B4),
                )
                Text(
                    "나에게 보내는 발렌타인 메시지",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFFF1493),
                )
            }
            Spacer(Modifier.height(12.dp))
            Text(
                message,
                style = MaterialTheme.typography.bodyMedium,
                fontStyle = FontStyle.Italic,
                color = MaterialTheme.colorScheme.onSurface,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun MbtiChip(mbti: String, valentine: Boolean = false) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = if (valentine) Color(0xFFFF69B4).copy(alpha = 0.2f)
                else MaterialTheme.colorScheme.secondaryContainer,
    ) {
        Text(
            mbti,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = if (valentine) Color(0xFFFF1493)
                    else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}
