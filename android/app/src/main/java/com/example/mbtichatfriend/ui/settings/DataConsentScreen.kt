package com.example.mbtichatfriend.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * AI 학습 데이터 활용 opt-in 동의 화면 — 10차 스프린트.
 *
 * 법무 요건 (10차 회의):
 * 1. 명시적 체크박스 (기본값 미선택)
 * 2. 목적 명시 ("AI 캐릭터 품질 개선")
 * 3. 철회 권리 안내
 * 4. 제3자 제공 없음 명시
 *
 * POST /api/v1/data/consent 연동.
 */
@Composable
fun DataConsentScreen(
    initialConsented: Boolean = false,
    onConfirm: (consented: Boolean) -> Unit,
    onClose: () -> Unit,
) {
    var isConsented by remember { mutableStateOf(initialConsented) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "AI 캐릭터 개선 참여",
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )

        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
            ),
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = "활용 목적",
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    text = "익명화된 대화 패턴이 AI 캐릭터의 말투와 공감 능력을 개선하는 데 활용됩니다.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                HorizontalDivider()
                Text(
                    text = "보장 사항",
                    style = MaterialTheme.typography.titleSmall,
                )
                listOf(
                    "이름, 연락처 등 식별 정보는 제거됩니다",
                    "제3자에게 제공되지 않습니다",
                    "언제든 동의를 철회할 수 있습니다",
                    "철회 시 기존 데이터는 삭제됩니다",
                ).forEach { item ->
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Text("•", style = MaterialTheme.typography.bodyMedium)
                        Text(item, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Checkbox(
                checked = isConsented,
                onCheckedChange = { isConsented = it },
            )
            Text(
                text = "AI 캐릭터 개선을 위한 익명화 데이터 활용에 동의합니다 (선택)",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = { onConfirm(isConsented) },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (isConsented) "동의하고 계속" else "동의하지 않고 계속")
        }

        TextButton(
            onClick = onClose,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("나중에 설정에서 변경")
        }
    }
}
