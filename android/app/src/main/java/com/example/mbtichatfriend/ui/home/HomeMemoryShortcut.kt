package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoStories
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/**
 * 홈 화면 '오늘의 기억' 숏컷 카드 — 7차 스프린트 (투자 UX 강화).
 *
 * 리텐션 데이터: 투자 사용자 30일 리텐션 68.1% vs 비투자 31.3% (2.2×).
 * 투자 진입점을 홈 화면으로 가져와 memory_saved 이벤트 빈도를 높인다.
 *
 * @param memoryCount 오늘 저장된 기억 수
 * @param characterName 현재 캐릭터 이름
 * @param onClick 기억 앨범 화면으로 이동
 */
@Composable
fun HomeMemoryShortcut(
    memoryCount: Int,
    characterName: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .semantics { contentDescription = "$characterName 와의 기억 앨범, 오늘 ${memoryCount}개 저장됨" },
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
        ),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.AutoStories,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSecondaryContainer,
            )
            Column {
                Text(
                    text = "우리의 이야기",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
                Text(
                    text = if (memoryCount > 0) "오늘 ${memoryCount}개의 순간을 저장했어요"
                           else "$characterName 와의 특별한 순간을 저장해보세요",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
            }
        }
    }
}
