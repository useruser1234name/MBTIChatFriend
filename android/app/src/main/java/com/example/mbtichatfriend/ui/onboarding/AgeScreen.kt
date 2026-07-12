package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.model.AgeGroup
import com.example.mbtichatfriend.ui.components.OnboardingScaffold

@Composable
fun AgeScreen(
    viewModel: OnboardingViewModel,
    onNext: () -> Unit,
    onBack: () -> Unit
) {
    OnboardingScaffold(
        step = 3,
        totalSteps = 5,
        title = "나이대를 선택해주세요",
        subtitle = "적절한 대화 수위를 맞춰드려요",
        onNext = onNext,
        onBack = onBack,
        // U5: 민감 정보 선택화 — 건너뛰면 기존 기본값(AgeGroup.TWENTIES)을 그대로 유지한 채
        // "다음" 버튼과 동일한 네비게이션 경로(onNext)로 진행. 서버로는 애초에 전송되지 않는 값(로컬 DataStore·Firestore 백업 전용).
        onSkip = {
            viewModel.updateAgeGroup(AgeGroup.TWENTIES)
            onNext()
        }
    ) {
        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            AgeGroup.entries.forEach { age ->
                val isSelected = viewModel.ageGroup == age
                SelectionButton(
                    text = age.label,
                    isSelected = isSelected,
                    onClick = { viewModel.updateAgeGroup(age) }
                )
            }
        }
    }
}
