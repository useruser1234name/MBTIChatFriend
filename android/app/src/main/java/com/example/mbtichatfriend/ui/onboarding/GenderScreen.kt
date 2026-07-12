package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.mbtichatfriend.model.Gender
import com.example.mbtichatfriend.ui.components.OnboardingScaffold

@Composable
fun GenderScreen(
    viewModel: OnboardingViewModel,
    onNext: () -> Unit,
    onBack: () -> Unit
) {
    OnboardingScaffold(
        step = 2,
        totalSteps = 5,
        title = "성별을 선택해주세요",
        subtitle = "캐릭터가 대화 톤을 맞춰줘요",
        onNext = onNext,
        onBack = onBack,
        // U5: 민감 정보 선택화 — 건너뛰면 기존 기본값(Gender.MALE)을 그대로 유지한 채
        // "다음" 버튼과 동일한 네비게이션 경로(onNext)로 진행. 서버로는 애초에 전송되지 않는 값(로컬 DataStore·Firestore 백업 전용).
        onSkip = {
            viewModel.updateGender(Gender.MALE)
            onNext()
        }
    ) {
        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Gender.entries.forEach { gender ->
                val isSelected = viewModel.gender == gender
                val label = when (gender) {
                    Gender.MALE -> "남성"
                    Gender.FEMALE -> "여성"
                    Gender.OTHER -> "기타"
                }
                SelectionButton(
                    text = label,
                    isSelected = isSelected,
                    onClick = { viewModel.updateGender(gender) }
                )
            }
        }
    }
}

@Composable
fun SelectionButton(
    text: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp),
        shape = RoundedCornerShape(16.dp),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (isSelected)
                MaterialTheme.colorScheme.primaryContainer
            else
                MaterialTheme.colorScheme.surface,
            contentColor = if (isSelected)
                MaterialTheme.colorScheme.onPrimaryContainer
            else
                MaterialTheme.colorScheme.onSurface
        ),
        border = BorderStroke(
            width = if (isSelected) 2.dp else 1.dp,
            color = if (isSelected)
                MaterialTheme.colorScheme.primary
            else
                MaterialTheme.colorScheme.outline
        )
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.titleMedium
        )
    }
}
