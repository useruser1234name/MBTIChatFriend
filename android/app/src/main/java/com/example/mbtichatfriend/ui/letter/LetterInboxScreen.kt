package com.example.mbtichatfriend.ui.letter

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * 캐릭터 편지 봉투 언박싱 화면 — 7차 스프린트.
 * PSY 화이트리스트 기반 편지 표시. 월 1회, opt-in.
 *
 * 흐름:
 * 1. 봉투 아이콘 표시 (Lottie: envelope_closed.json)
 * 2. 사용자 탭 → 봉투 열리는 애니메이션 (Lottie: envelope_open.json)
 * 3. 편지 내용 fade-in
 */
@Composable
fun LetterInboxScreen(
    characterName: String,
    letterContent: String,
    generatedDate: String,
    onClose: () -> Unit,
) {
    var isOpened by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = "$characterName 의 편지",
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )

        Spacer(modifier = Modifier.height(32.dp))

        if (!isOpened) {
            // 봉투 닫힌 상태
            EnvelopeClosedView(
                characterName = characterName,
                onTap = { isOpened = true },
            )
        } else {
            // 봉투 열린 후 편지 내용
            AnimatedVisibility(
                visible = true,
                enter = fadeIn(tween(600)) + expandVertically(),
            ) {
                LetterContentCard(
                    characterName = characterName,
                    content = letterContent,
                    date = generatedDate,
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        if (isOpened) {
            Button(onClick = onClose) {
                Text("편지 보관하기")
            }
        }
    }
}

@Composable
private fun EnvelopeClosedView(
    characterName: String,
    onTap: () -> Unit,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Lottie envelope_closed.json — 실제 JSON 파일은 assets/lottie/에 추가 필요
        // 현재는 텍스트 이모지로 대체 (Lottie 파일 준비 후 LottieAnimation으로 교체)
        Text(text = "✉️", style = MaterialTheme.typography.displayLarge)

        Text(
            text = "$characterName 이(가) 편지를 남겼어요",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
        )

        OutlinedButton(onClick = onTap) {
            Text("편지 열기")
        }
    }
}

@Composable
private fun LetterContentCard(
    characterName: String,
    content: String,
    date: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "To. 너에게",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = content,
                style = MaterialTheme.typography.bodyLarge,
                lineHeight = MaterialTheme.typography.bodyLarge.lineHeight,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "From. $characterName  ($date)",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}
