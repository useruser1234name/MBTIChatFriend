package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.ui.theme.PastelPink
import com.example.mbtichatfriend.ui.theme.PastelPinkLight

private val DEFAULT_STARTERS = listOf(
    "안녕! 오늘 어떤 하루였어?",
    "요즘 뭐가 제일 재밌어?",
    "나한테 뭐든 털어놔도 돼"
)

/**
 * 온보딩 마지막 단계 — 대화 스타터 선택.
 * 10차 스프린트 (QS 75% 달성 전략 — UX-A 구민지).
 *
 * 서버 GET /api/v1/chat/starters 에서 MBTI 맞춤 스타터 3개 로드.
 * 첫 번째 스타터 디폴트 선택, 사용자 변경 가능.
 * 선택된 스타터로 채팅 첫 턴 자동 입력.
 *
 * 온보딩 이탈 목표: MBTI 단계 38% → 15%
 *
 * A8 UX 개선 (2026-06-03):
 * - FilterChip → 채팅 말풍선 UI로 변경
 * - "직접 입력하기" → "내 말로 시작하기" 문구 변경
 * - 레퍼럴 코드 섹션을 이 화면에서 제거 (첫 대화 집중도 향상)
 *   레퍼럴 진입점: Settings 화면 > "초대 코드 입력" 섹션으로 위임
 *   (Settings에 해당 섹션이 없을 경우 추가 예정 — TODO: SettingsScreen 레퍼럴 섹션)
 */
@Composable
fun StarterSelectionScreen(
    characterName: String,
    starters: List<String>,
    isLoading: Boolean,
    onStarterConfirmed: (selectedStarter: String) -> Unit,
    viewModel: OnboardingViewModel,
    modifier: Modifier = Modifier,
) {
    // 로딩 중이거나 API 결과가 비어있으면 DEFAULT_STARTERS로 fallback
    val displayStarters = when {
        isLoading -> DEFAULT_STARTERS
        starters.isEmpty() -> DEFAULT_STARTERS
        else -> starters
    }

    // 첫 번째 스타터 디폴트 선택
    var selectedStarter by remember(displayStarters) {
        mutableStateOf(displayStarters.firstOrNull() ?: "")
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "$characterName 에게 첫 마디를 건네볼까요?",
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )

        Text(
            text = "아래 중 하나를 선택하거나, 직접 입력할 수 있어요",
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        // 말풍선 스타터 목록 — 사용자가 실제로 그 문장을 말한 듯한 UI
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            displayStarters.forEach { starter ->
                StarterBubble(
                    text = starter,
                    isSelected = selectedStarter == starter,
                    onClick = { selectedStarter = starter },
                )
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        Button(
            onClick = {
                if (selectedStarter.isNotEmpty()) {
                    onStarterConfirmed(selectedStarter)
                }
            },
            enabled = selectedStarter.isNotEmpty(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("대화 시작하기")
        }

        TextButton(
            onClick = { onStarterConfirmed("") },  // 스타터 없이 시작
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("내 말로 시작하기")
        }
    }
}

/**
 * 채팅 말풍선 모양 스타터 아이템.
 * 선택된 항목: 파스텔 핑크 배경 + 진한 테두리로 강조.
 * 미선택 항목: 반투명 배경 + 흐린 테두리.
 *
 * 꼬리는 우측 하단(사용자 말풍선 방향)에 위치.
 */
@Composable
private fun StarterBubble(
    text: String,
    isSelected: Boolean,
    onClick: () -> Unit,
) {
    val bubbleBackground = if (isSelected) PastelPink else PastelPinkLight.copy(alpha = 0.35f)
    val borderColor = if (isSelected) PastelPink else PastelPink.copy(alpha = 0.30f)
    val textColor = if (isSelected) MaterialTheme.colorScheme.onSurface
                    else MaterialTheme.colorScheme.onSurfaceVariant

    val bubbleShape = RoundedCornerShape(
        topStart = 16.dp,
        topEnd = 16.dp,
        bottomStart = 16.dp,
        bottomEnd = 4.dp,     // 사용자 말풍선: 우측 하단 꼬리 효과
    )

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(bubbleShape)
            .background(bubbleBackground, bubbleShape)
            .border(
                width = if (isSelected) 1.5.dp else 1.dp,
                color = borderColor,
                shape = bubbleShape,
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyLarge,
            color = textColor,
        )
    }
}
