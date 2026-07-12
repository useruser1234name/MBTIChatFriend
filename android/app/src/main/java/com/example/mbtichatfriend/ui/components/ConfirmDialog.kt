package com.example.mbtichatfriend.ui.components

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * 공용 확인/취소 AlertDialog (A3).
 *
 * 4개 사이트(ChatScreen 대화 초기화·공유 확인, HomeScreen 캐릭터 삭제,
 * SettingsScreen 로그아웃)의 title/text/확인·취소 버튼 패턴이 동일해 통합했다.
 * 비즈니스 로직은 각 호출부의 [onConfirm] 람다에 그대로 유지한다.
 *
 * [confirmColor] 기본값은 TextButton의 기본 contentColor(MaterialTheme.colorScheme.primary)와
 * 동일해, 색을 넘기지 않는 사이트(공유 확인)의 렌더링이 기존과 동일하게 유지된다.
 * 삭제/로그아웃처럼 강조가 필요한 사이트만 MaterialTheme.colorScheme.error를 넘긴다.
 */
@Composable
fun ConfirmDialog(
    title: String,
    text: String,
    confirmLabel: String,
    dismissLabel: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    confirmColor: Color = MaterialTheme.colorScheme.primary,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                colors = ButtonDefaults.textButtonColors(contentColor = confirmColor)
            ) {
                Text(confirmLabel)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(dismissLabel)
            }
        }
    )
}
