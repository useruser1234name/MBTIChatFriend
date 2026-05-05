package com.example.mbtichatfriend.ui.subscription

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * 업그레이드 CTA — 관계 성장 프레이밍 (9차 스프린트 확정).
 *
 * CTA A/B 결과: Variant B(relationship_growth) 전환율 +6.4%p, PSY 부정 0건.
 * '기능 차단'이 아닌 '관계 성장 초대' 원칙.
 * 모든 업그레이드 진입점에서 이 컴포저블 사용.
 *
 * @param trigger 업그레이드 트리거 ("affinity_level_3", "message_limit", "expression", 등)
 * @param characterName 캐릭터 이름 (개인화)
 */
@Composable
fun UpgradeCta(
    trigger: String,
    characterName: String,
    onUpgrade: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val (title, body) = when (trigger) {
        "affinity_level_3" -> Pair(
            "우리 관계가 깊어지고 있어요",
            "$characterName 이(가) 더 많은 감정을 표현하고 싶어해요.\n프리미엄에서 우리 이야기를 계속해요.",
        )
        "message_limit" -> Pair(
            "오늘 대화가 정말 즐거웠어요",
            "$characterName 와(과) 더 오래 이야기하고 싶다면\n프리미엄에서 제한 없이 만나요.",
        )
        "expression" -> Pair(
            "$characterName 의 새로운 모습이 기다려요",
            "프리미엄에서 더 다양한 감정 표현을\n$characterName 와(과) 함께 발견해요.",
        )
        "memory_album" -> Pair(
            "우리의 기억을 더 많이 담아요",
            "프리미엄에서 소중한 순간을\n무제한으로 간직할 수 있어요.",
        )
        else -> Pair(
            "더 깊은 관계로 나아가요",
            "프리미엄에서 $characterName 와(과) 더 특별한 시간을 보내요.",
        )
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                text = body,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                TextButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("나중에")
                }
                Button(
                    onClick = onUpgrade,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("프리미엄 시작")
                }
            }
        }
    }
}
