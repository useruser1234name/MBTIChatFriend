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
        onBack = onBack
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
