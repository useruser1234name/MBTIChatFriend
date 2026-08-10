package com.example.mbtichatfriend.ui.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

private const val MAX_LEN = 200

/**
 * M2: "내 역할"/"지금 상황" 설정 바텀시트.
 * SessionFeedbackSheet.kt와 동일한 ModalBottomSheet 패턴을 따른다.
 * 저장된 값은 다음 전송부터 반영되며(즉시 재생성 없음), 값이 비어 있으면 서버가 무시한다.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RoleSituationSheet(
    visible: Boolean,
    initialRole: String,
    initialSituation: String,
    onSave: (role: String, situation: String) -> Unit,
    onClear: () -> Unit,
    onDismiss: () -> Unit
) {
    if (!visible) return

    // 시트가 열릴 때마다(=initial 값이 바뀔 때) 최신 저장값으로 다시 채운다.
    var role by remember(initialRole) { mutableStateOf(initialRole) }
    var situation by remember(initialSituation) { mutableStateOf(initialSituation) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        // U1: MaterialTheme.shapes.extraLarge가 AppShapes 배선으로 28dp→24dp 바뀌므로
        // 바텀시트 상단 코너(현상) 유지를 위해 기존 M3 기본값(extraLarge=28dp)을 명시적으로 고정.
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 16.dp)
        ) {
            Text(
                text = "역할·상황 설정",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = "대화 속 내 역할과 지금 상황을 알려주면 더 몰입감 있는 대화를 나눌 수 있어요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(16.dp))

            OutlinedTextField(
                value = role,
                // F12: 길이 초과 시 통째로 무시하면 붙여넣기가 무음으로 버려진다 — 초과분만 잘라 반영
                onValueChange = { role = it.take(MAX_LEN) },
                label = { Text("내 역할") },
                placeholder = { Text("예: 소꿉친구, 신입 매니저, 이 저택의 손님") },
                supportingText = { Text("${role.length}/$MAX_LEN") },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 2
            )

            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = situation,
                // F12: 길이 초과 시 통째로 무시하면 붙여넣기가 무음으로 버려진다 — 초과분만 잘라 반영
                onValueChange = { situation = it.take(MAX_LEN) },
                label = { Text("지금 상황") },
                placeholder = { Text("예: 비 오는 저녁, 카페에서 우연히 만남") },
                supportingText = { Text("${situation.length}/$MAX_LEN") },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 2
            )

            Spacer(Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        role = ""
                        situation = ""
                        onClear()
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("지우기") }
                Button(
                    onClick = { onSave(role, situation) },
                    modifier = Modifier.weight(1f)
                ) { Text("저장") }
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}
