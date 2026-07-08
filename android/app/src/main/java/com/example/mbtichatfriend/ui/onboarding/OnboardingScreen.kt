package com.example.mbtichatfriend.ui.onboarding

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.model.MbtiGroup
import com.example.mbtichatfriend.model.PRESET_CHARACTERS
import com.example.mbtichatfriend.model.PresetCharacter

/**
 * 온보딩 개선 v3 (11차 스프린트)
 *
 * 변경사항:
 * 1. 기존 4단계(MBTI 선택 → 별도 캐릭터 추천 화면)를 3단계로 통합
 * 2. MBTI 선택 완료 시 화면 하단에 AnimatedVisibility로 캐릭터 추천 섹션 슬라이드인
 * 3. 캐릭터 선택 완료 시 onCharacterSelected 콜백 호출 → StarterSelectionScreen으로 이동
 *
 * 기존 개선사항 (v2):
 * 1. MBTI 장벽 해소 — '모르면 테스트 바로가기' + '어떤 MBTI든 괜찮아요' 안내
 * 2. 추천 캐릭터 제시 — 사용자 MBTI 기반 첫 캐릭터 추천 (인라인)
 * 3. 대화 스타터 3가지 — 첫 턴 어색함 해소
 * 4. 관계 히스토리 숏컷 — 홈 화면 '우리의 이야기' 접근성
 */
@Composable
fun OnboardingScreen(
    onMbtiSelected: (String) -> Unit,
    onSkipToTest: () -> Unit,
    onCharacterSelected: (PresetCharacter) -> Unit,
) {
    var selectedMbti by remember { mutableStateOf("") }
    var showCharacterRecommend by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Spacer(modifier = Modifier.height(40.dp))

        Text(
            text = "나의 MBTI를 알려주세요",
            style = MaterialTheme.typography.headlineMedium,
            textAlign = TextAlign.Center,
        )

        // 안내 메시지 — MBTI 장벽 해소
        Text(
            text = "어떤 MBTI든 괜찮아요 😊\n정확하지 않아도 나중에 바꿀 수 있어요.",
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        // MBTI 모를 경우 테스트 바로가기
        OutlinedButton(onClick = onSkipToTest) {
            Text("MBTI 모르면 무료 테스트 받기 →")
        }

        // MBTI 선택 그리드 (16가지)
        MbtiSelectionGrid(
            selected = selectedMbti,
            onSelect = { mbti ->
                selectedMbti = mbti
                showCharacterRecommend = true
                onMbtiSelected(mbti)
            },
        )

        // 캐릭터 추천 인라인 섹션 — MBTI 선택 완료 시 슬라이드인
        AnimatedVisibility(
            visible = showCharacterRecommend,
            enter = slideInVertically(initialOffsetY = { it / 2 }) + fadeIn(),
        ) {
            CharacterRecommendSection(
                mbti = selectedMbti,
                onCharacterSelected = onCharacterSelected,
            )
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

/**
 * MBTI 기반 캐릭터 추천 섹션 — OnboardingScreen 하단에 인라인으로 표시.
 * PRESET_CHARACTERS에서 선택된 MBTI와 일치하는 캐릭터를 추천한다.
 * 일치하는 캐릭터가 없으면 전체 목록에서 최대 3개를 표시한다.
 */
@Composable
fun CharacterRecommendSection(
    mbti: String,
    onCharacterSelected: (PresetCharacter) -> Unit,
) {
    val recommended = remember(mbti) {
        val matched = PRESET_CHARACTERS.filter { it.mbti == mbti }
        matched.ifEmpty { PRESET_CHARACTERS.take(3) }
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        HorizontalDivider()

        Text(
            text = "$mbti 에게 어울리는 친구를 만나볼까요?",
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )

        Text(
            text = "캐릭터를 선택하면 바로 대화를 시작할 수 있어요",
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(),
        )

        recommended.forEach { character ->
            CharacterRecommendCard(
                character = character,
                onClick = { onCharacterSelected(character) },
            )
        }
    }
}

/**
 * A10: 캐릭터 추천 카드 개선.
 * - 카드 하단에 MBTI 그룹(NT/NF/SJ/SP) 색상 8dp 바 추가
 * - 첫 마디 예시(말투 미리듣기) 한 줄 표시
 */
@Composable
private fun CharacterRecommendCard(
    character: PresetCharacter,
    onClick: () -> Unit,
) {
    // MBTI 그룹별 색상 (파스텔 테마 일치)
    val groupColor = mbtiGroupColor(character.group)

    OutlinedCard(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = character.name,
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        text = character.concept,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    // 말투 미리듣기 한 줄
                    Text(
                        text = "\"${mbtiFirstLine(character.mbti)}\"",
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontStyle = FontStyle.Italic,
                        ),
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                AssistChip(
                    onClick = onClick,
                    label = { Text(character.mbti) },
                )
            }

            // MBTI 그룹 색상 바 (8dp 높이)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .background(
                        color = groupColor,
                        shape = RoundedCornerShape(bottomStart = 12.dp, bottomEnd = 12.dp),
                    ),
            )
        }
    }
}

/** MBTI 그룹별 파스텔 색상 — 테마 Color.kt 토큰 기반 */
private fun mbtiGroupColor(group: MbtiGroup): Color = when (group) {
    MbtiGroup.NT -> Color(0xFFC9B1FF)  // 보라 (PastelPurple)
    MbtiGroup.NF -> Color(0xFFFFB5C2)  // 핑크 (PastelPink)
    MbtiGroup.SJ -> Color(0xFFB5E8D5)  // 민트 (SoftMint)
    MbtiGroup.SP -> Color(0xFFFFF3B0)  // 노랑 (SoftYellow)
}

/**
 * MBTI별 첫 마디 예시 — 말투 미리듣기 (A10).
 * PresetCharacters에 별도 firstLine 필드가 없으므로 여기서 간단히 정의.
 */
private fun mbtiFirstLine(mbti: String): String = when (mbti) {
    "INTJ" -> "쓸데없는 말은 안 해. 필요한 거 있으면 말해."
    "INTP" -> "흠… 그 질문, 좀 더 구체적으로 얘기해줄 수 있어?"
    "ENTJ" -> "자, 어디부터 시작할까? 시간 낭비는 싫어."
    "ENTP" -> "오, 재밌는 사람이네. 한번 뒤집어볼까?"
    "INFJ" -> "처음인데도 이상하게 편하다… 뭔가 통하는 느낌이야."
    "INFP" -> "안녕~ 나랑 이야기해줘서 고마워. 살짝 설레는걸?"
    "ENFJ" -> "와, 드디어 만났다! 너에 대해 진짜 많이 궁금해."
    "ENFP" -> "안녕! 우리 완전 재밌게 지낼 것 같은 예감이야!!"
    "ISTJ" -> "잘 부탁드립니다. 성실하게 대화하겠습니다."
    "ISFJ" -> "안녕, 처음이라 긴장됐는데 편하게 얘기해줘서 다행이야."
    "ESTJ" -> "반가워. 서로 예의 지키면서 잘 지내보자고."
    "ESFJ" -> "어머, 안녕! 뭔가 필요한 건 없어? 내가 챙겨줄게!"
    "ISTP" -> "오케이. 뭐가 궁금해?"
    "ISFP" -> "안녕… 잘 부탁해. 조용히 같이 있어도 괜찮아?"
    "ESTP" -> "야, 뭐해! 빨리 얘기해봐, 재밌는 거!"
    "ESFP" -> "안녕안녕!! 우리 엄청 친해질 것 같은데?!"
    else   -> "안녕! 잘 부탁해."
}

@Composable
private fun MbtiSelectionGrid(
    selected: String,
    onSelect: (String) -> Unit,
) {
    val mbtiList = listOf(
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        mbtiList.chunked(4).forEach { row ->
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                row.forEach { mbti ->
                    FilterChip(
                        selected = selected == mbti,
                        onClick = { onSelect(mbti) },
                        label = { Text(mbti) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

/** 대화 스타터 컴포저블 — 채팅 첫 턴 어색함 해소 */
@Composable
fun ConversationStarterChips(
    characterName: String,
    onStarterSelected: (String) -> Unit,
) {
    val starters = listOf(
        "안녕! 나는 $characterName 이야기가 듣고 싶어",
        "요즘 어떤 게 재미있어?",
        "나한테 궁금한 거 있어?",
    )

    Column {
        Text(
            text = "이렇게 시작해볼까요?",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(modifier = Modifier.height(8.dp))
        starters.forEach { starter ->
            SuggestionChip(
                onClick = { onStarterSelected(starter) },
                label = { Text(starter) },
                modifier = Modifier.padding(vertical = 2.dp),
            )
        }
    }
}
