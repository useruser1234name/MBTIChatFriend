package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.model.Relationship
import com.example.mbtichatfriend.model.SpeechStyle
import com.example.mbtichatfriend.ui.components.OnboardingScaffold

@Composable
fun StyleSelectScreen(
    viewModel: OnboardingViewModel,
    onComplete: () -> Unit,
    onBack: () -> Unit
) {
    OnboardingScaffold(
        step = 5,
        totalSteps = 5,
        title = "대화 스타일을\n선택해주세요",
        subtitle = "캐릭터의 말투와 관계를 정해요",
        buttonText = "대화 시작하기",
        onNext = { viewModel.saveOnboarding(onComplete) },
        onBack = onBack
    ) {
        Column {
            // 말투 선택
            Text(
                text = "말투",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(Modifier.height(8.dp))
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SpeechStyle.entries.forEach { style ->
                    SelectionButton(
                        text = style.label,
                        isSelected = viewModel.speechStyle == style,
                        onClick = { viewModel.updateSpeechStyle(style) }
                    )
                }
            }

            Spacer(Modifier.height(24.dp))

            // 관계 선택
            Text(
                text = "관계",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(Modifier.height(8.dp))
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Relationship.entries.forEach { rel ->
                    SelectionButton(
                        text = rel.label,
                        isSelected = viewModel.relationship == rel,
                        onClick = { viewModel.updateRelationship(rel) }
                    )
                }
            }
        }
    }
}
