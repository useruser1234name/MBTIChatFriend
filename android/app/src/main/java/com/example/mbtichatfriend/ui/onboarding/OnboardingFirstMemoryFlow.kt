package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoStories
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Day 1 투자 유도 — 첫 채팅 후 '첫 번째 기억 저장' 유도 플로우.
 * 8차 스프린트 (8차 회의 합의 — UX-A 구민지).
 *
 * 리텐션 데이터 근거:
 * - 투자 사용자 30일 리텐션 71.3% vs 비투자 32.1%
 * - 첫 날 투자 경험이 장기 리텐션에 결정적
 *
 * 사용: 첫 채팅 3턴 완료 후 표시 (isVisible = turn_count >= 3 && !hasMemory)
 */
@Composable
fun OnboardingFirstMemoryPrompt(
    characterName: String,
    firstMessagePreview: String,
    isVisible: Boolean,
    onSaveMemory: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = isVisible,
        enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(),
        modifier = modifier,
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.primaryContainer,
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.AutoStories,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onPrimaryContainer,
                    modifier = Modifier.size(32.dp),
                )
                Text(
                    text = "$characterName 와의 첫 번째 이야기",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    textAlign = TextAlign.Center,
                )
                if (firstMessagePreview.isNotEmpty()) {
                    Text(
                        text = "\"${firstMessagePreview.take(40)}${if (firstMessagePreview.length > 40) "..." else ""}\"",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.8f),
                        textAlign = TextAlign.Center,
                    )
                }
                Text(
                    text = "이 순간을 기억 앨범에 저장해볼까요?",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    textAlign = TextAlign.Center,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("다음에")
                    }
                    Button(
                        onClick = onSaveMemory,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("저장하기")
                    }
                }
            }
        }
    }
}
