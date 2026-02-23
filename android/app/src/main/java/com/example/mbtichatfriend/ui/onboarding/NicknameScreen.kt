package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.ui.components.OnboardingScaffold

@Composable
fun NicknameScreen(
    viewModel: OnboardingViewModel,
    onNext: () -> Unit
) {
    OnboardingScaffold(
        step = 1,
        totalSteps = 5,
        title = "닉네임을 알려주세요",
        subtitle = "캐릭터가 당신을 부를 이름이에요",
        buttonEnabled = viewModel.isNicknameValid,
        onNext = onNext
    ) {
        Column {
            OutlinedTextField(
                value = viewModel.nickname,
                onValueChange = viewModel::updateNickname,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("2~8자 닉네임") },
                singleLine = true,
                shape = RoundedCornerShape(16.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface
                ),
                isError = viewModel.nicknameError != null && viewModel.nickname.isNotEmpty()
            )

            if (viewModel.nicknameError != null && viewModel.nickname.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    text = viewModel.nicknameError!!,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }

            Spacer(Modifier.height(8.dp))

            Text(
                text = "${viewModel.nickname.length}/8",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
