package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

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

    // 레퍼럴 코드 상태 (17차 스프린트)
    var referralCodeExpanded by remember { mutableStateOf(false) }
    var referralCode by remember { mutableStateOf("") }
    var referralApplied by remember { mutableStateOf(false) }
    var referralError by remember { mutableStateOf<String?>(null) }

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

        displayStarters.forEach { starter ->
            FilterChip(
                selected = selectedStarter == starter,
                onClick = { selectedStarter = starter },
                label = {
                    Text(
                        text = starter,
                        modifier = Modifier.padding(vertical = 4.dp),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        // ── 초대 코드 Expandable 섹션 (17차 스프린트) ────────────────────────
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            shape = MaterialTheme.shapes.medium,
            tonalElevation = 1.dp
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { referralCodeExpanded = !referralCodeExpanded },
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "초대 코드가 있으신가요?",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Icon(
                        imageVector = if (referralCodeExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                AnimatedVisibility(visible = referralCodeExpanded) {
                    Column(modifier = Modifier.padding(top = 12.dp)) {
                        if (referralApplied) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.CheckCircle,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(20.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "초대 코드가 적용됐어요! 프리미엄 3일이 추가됩니다.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        } else {
                            OutlinedTextField(
                                value = referralCode,
                                onValueChange = { referralCode = it.uppercase().take(8) },
                                label = { Text("초대 코드 8자리") },
                                placeholder = { Text("예: AB12CD34") },
                                singleLine = true,
                                isError = referralError != null,
                                supportingText = referralError?.let {
                                    { Text(it, color = MaterialTheme.colorScheme.error) }
                                },
                                trailingIcon = {
                                    if (referralCode.length == 8) {
                                        IconButton(onClick = {
                                            viewModel.redeemReferralCode(referralCode) { success, error ->
                                                if (success) {
                                                    referralApplied = true
                                                    referralError = null
                                                } else {
                                                    referralError = error ?: "코드를 확인해 주세요."
                                                }
                                            }
                                        }) {
                                            Icon(Icons.Default.Check, contentDescription = "코드 적용")
                                        }
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                                keyboardOptions = KeyboardOptions(
                                    capitalization = KeyboardCapitalization.Characters,
                                    imeAction = ImeAction.Done
                                )
                            )
                        }
                    }
                }
            }
        }
        // ─────────────────────────────────────────────────────────────────────

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
            Text("직접 입력하기")
        }
    }
}
