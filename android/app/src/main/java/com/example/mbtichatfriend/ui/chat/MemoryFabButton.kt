package com.example.mbtichatfriend.ui.chat

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/**
 * '이 순간 저장' 플로팅 버튼 — 7차 스프린트 (투자 UX 강화).
 *
 * 투자 이벤트 'memory_saved'를 유발하는 핵심 진입점.
 * 감동적인 대화 직후 visible=true로 설정하여 표시.
 *
 * 사용: ChatScreen에서 emotionScore > threshold 시 visible = true
 */
@Composable
fun MemoryFabButton(
    visible: Boolean,
    onSave: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(),
        modifier = modifier,
    ) {
        ExtendedFloatingActionButton(
            onClick = onSave,
            icon = {
                Icon(
                    imageVector = Icons.Filled.Favorite,
                    contentDescription = null,
                )
            },
            text = { Text("이 순간 저장") },
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            modifier = Modifier.semantics {
                contentDescription = "이 대화를 기억 앨범에 저장합니다"
            },
        )
    }
}
