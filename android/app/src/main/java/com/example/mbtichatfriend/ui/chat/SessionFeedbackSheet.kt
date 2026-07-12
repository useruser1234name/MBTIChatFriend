package com.example.mbtichatfriend.ui.chat

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionFeedbackSheet(
    visible: Boolean,
    onSubmit: (rating: Int, text: String?) -> Unit,
    onDismiss: () -> Unit
) {
    if (!visible) return

    var rating by remember { mutableStateOf(0) }
    var feedbackText by remember { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        // U1: MaterialTheme.shapes.extraLarge가 AppShapes 배선으로 28dp→24dp 바뀌므로
        // 바텀시트 상단 코너(현상) 유지를 위해 기존 M3 기본값(extraLarge=28dp)을 명시적으로 고정.
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "오늘 대화는 어땠어요?",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(modifier = Modifier.height(16.dp))

            // 별점 5개 Row
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                (1..5).forEach { star ->
                    IconButton(onClick = { rating = star }) {
                        Icon(
                            imageVector = if (star <= rating) Icons.Filled.Star else Icons.Outlined.StarOutline,
                            contentDescription = "별점 $star",
                            tint = if (star <= rating) MaterialTheme.colorScheme.primary
                                   else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(36.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 선택적 텍스트 입력
            OutlinedTextField(
                value = feedbackText,
                onValueChange = { feedbackText = it },
                placeholder = { Text("한 마디 남겨줄래요? (선택)") },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 3
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f)
                ) { Text("나중에") }
                Button(
                    onClick = {
                        if (rating > 0) {
                            onSubmit(rating, feedbackText.ifBlank { null })
                        }
                    },
                    enabled = rating > 0,
                    modifier = Modifier.weight(1f)
                ) { Text("남기기") }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}
