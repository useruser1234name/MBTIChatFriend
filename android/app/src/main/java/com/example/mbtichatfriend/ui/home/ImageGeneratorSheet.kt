package com.example.mbtichatfriend.ui.home

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageGenerateRequest
import com.example.mbtichatfriend.model.MbtiType
import com.example.mbtichatfriend.model.Relationship
import com.example.mbtichatfriend.model.SpeechStyle
import kotlinx.coroutines.launch

data class StyleOption(val label: String, val promptEn: String)

private val artStyles = listOf(
    StyleOption("일본 애니메이션", "Japanese anime style"),
    StyleOption("한국 웹툰", "Korean webtoon style"),
    StyleOption("실사풍", "photorealistic digital art"),
    StyleOption("수채화", "watercolor painting style"),
    StyleOption("판타지 일러스트", "fantasy illustration style")
)

private val hairOptions = listOf(
    StyleOption("긴 생머리", "long straight hair"),
    StyleOption("단발", "short bob hair"),
    StyleOption("웨이브", "long wavy hair"),
    StyleOption("포니테일", "ponytail hair"),
    StyleOption("트윈테일", "twin-tail hair"),
    StyleOption("짧은 머리", "short pixie hair")
)

private val vibeOptions = listOf(
    StyleOption("청순", "innocent and pure"),
    StyleOption("시크", "chic and cool"),
    StyleOption("밝은", "bright and cheerful"),
    StyleOption("신비로운", "mysterious and ethereal"),
    StyleOption("귀여운", "cute and adorable"),
    StyleOption("성숙한", "mature and elegant")
)

private val ethnicityOptions = listOf(
    StyleOption("동양인", "East Asian"),
    StyleOption("서양인", "Western European"),
    StyleOption("판타지", "fantasy character with elf ears")
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ImageGeneratorSheet(
    sheetState: SheetState,
    chatApi: ChatApi,
    onDismiss: () -> Unit,
    onCharacterCreated: (name: String, mbti: String, speechStyle: String, relationship: String, avatarId: String) -> Unit
) {
    val scope = rememberCoroutineScope()

    // Step 1 state
    var selectedArt by remember { mutableIntStateOf(0) }
    var selectedHair by remember { mutableIntStateOf(0) }
    var selectedVibe by remember { mutableIntStateOf(0) }
    var selectedEthnicity by remember { mutableIntStateOf(0) }
    var customPrompt by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var generatedImageUrl by remember { mutableStateOf<String?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    // Step 2 state
    var currentStep by remember { mutableIntStateOf(1) }
    var charName by remember { mutableStateOf("") }
    var selectedMbti by remember { mutableStateOf(MbtiType.ENFP) }
    var selectedStyle by remember { mutableStateOf(SpeechStyle.CASUAL) }
    var selectedRelationship by remember { mutableStateOf(Relationship.FRIEND) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState
    ) {
        AnimatedContent(
            targetState = currentStep,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "step"
        ) { step ->
            when (step) {
                1 -> Step1ImageGeneration(
                    selectedArt = selectedArt,
                    onArtSelect = { selectedArt = it },
                    selectedHair = selectedHair,
                    onHairSelect = { selectedHair = it },
                    selectedVibe = selectedVibe,
                    onVibeSelect = { selectedVibe = it },
                    selectedEthnicity = selectedEthnicity,
                    onEthnicitySelect = { selectedEthnicity = it },
                    customPrompt = customPrompt,
                    onCustomPromptChange = { customPrompt = it },
                    isLoading = isLoading,
                    generatedImageUrl = generatedImageUrl,
                    errorMessage = errorMessage,
                    onGenerate = {
                        scope.launch {
                            isLoading = true
                            errorMessage = null
                            try {
                                val prompt = buildPrompt(
                                    artStyles[selectedArt],
                                    hairOptions[selectedHair],
                                    vibeOptions[selectedVibe],
                                    ethnicityOptions[selectedEthnicity],
                                    customPrompt
                                )
                                val response = chatApi.generateImage(
                                    ImageGenerateRequest(prompt = prompt)
                                )
                                generatedImageUrl = response.url
                            } catch (e: Exception) {
                                errorMessage = "오류: ${e.localizedMessage ?: "알 수 없는 오류"}"
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    onNext = { currentStep = 2 }
                )
                2 -> Step2CharacterInfo(
                    imageUrl = generatedImageUrl!!,
                    charName = charName,
                    onNameChange = { if (it.length <= 8) charName = it },
                    selectedMbti = selectedMbti,
                    onMbtiSelect = { selectedMbti = it },
                    selectedStyle = selectedStyle,
                    onStyleSelect = { selectedStyle = it },
                    selectedRelationship = selectedRelationship,
                    onRelationshipSelect = { selectedRelationship = it },
                    onBack = { currentStep = 1 },
                    onCreate = {
                        val avatarId = "img:$generatedImageUrl"
                        onCharacterCreated(
                            charName, selectedMbti.name, selectedStyle.name,
                            selectedRelationship.name, avatarId
                        )
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Step1ImageGeneration(
    selectedArt: Int, onArtSelect: (Int) -> Unit,
    selectedHair: Int, onHairSelect: (Int) -> Unit,
    selectedVibe: Int, onVibeSelect: (Int) -> Unit,
    selectedEthnicity: Int, onEthnicitySelect: (Int) -> Unit,
    customPrompt: String, onCustomPromptChange: (String) -> Unit,
    isLoading: Boolean,
    generatedImageUrl: String?,
    errorMessage: String?,
    onGenerate: () -> Unit,
    onNext: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "이상형 만들기",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        Text(
            "STEP 1 - 이미지 생성",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(Modifier.height(16.dp))

        SectionTitle("그림체")
        ChipGroup(artStyles, selectedArt, onArtSelect)

        SectionTitle("머리 스타일")
        ChipGroup(hairOptions, selectedHair, onHairSelect)

        SectionTitle("분위기")
        ChipGroup(vibeOptions, selectedVibe, onVibeSelect)

        SectionTitle("인종")
        ChipGroup(ethnicityOptions, selectedEthnicity, onEthnicitySelect)

        SectionTitle("추가 설명 (선택)")
        OutlinedTextField(
            value = customPrompt,
            onValueChange = onCustomPromptChange,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("예: 파란 눈, 흰 드레스, 꽃밭 배경") },
            singleLine = false,
            maxLines = 2,
            shape = RoundedCornerShape(12.dp)
        )

        Spacer(Modifier.height(16.dp))

        AnimatedVisibility(visible = generatedImageUrl != null) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                AsyncImage(
                    model = generatedImageUrl,
                    contentDescription = "생성된 이미지",
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(1f)
                        .clip(RoundedCornerShape(16.dp)),
                    contentScale = ContentScale.Crop
                )
                Spacer(Modifier.height(12.dp))
            }
        }

        errorMessage?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(4.dp))
        }

        if (generatedImageUrl != null) {
            Button(
                onClick = onNext,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(16.dp)
            ) {
                Text("이 캐릭터로 만들기")
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onGenerate,
                modifier = Modifier.fillMaxWidth(),
                enabled = !isLoading,
                shape = RoundedCornerShape(16.dp)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Text("다시 생성하기")
                }
            }
        } else {
            Button(
                onClick = onGenerate,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                enabled = !isLoading,
                shape = RoundedCornerShape(16.dp)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("생성하기")
                }
            }
        }

        Spacer(Modifier.height(32.dp))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Step2CharacterInfo(
    imageUrl: String,
    charName: String, onNameChange: (String) -> Unit,
    selectedMbti: MbtiType, onMbtiSelect: (MbtiType) -> Unit,
    selectedStyle: SpeechStyle, onStyleSelect: (SpeechStyle) -> Unit,
    selectedRelationship: Relationship, onRelationshipSelect: (Relationship) -> Unit,
    onBack: () -> Unit,
    onCreate: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "이상형 만들기",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        Text(
            "STEP 2 - 캐릭터 설정",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(Modifier.height(16.dp))

        AsyncImage(
            model = imageUrl,
            contentDescription = "캐릭터 이미지",
            modifier = Modifier
                .size(120.dp)
                .clip(RoundedCornerShape(16.dp))
                .align(Alignment.CenterHorizontally),
            contentScale = ContentScale.Crop
        )

        Spacer(Modifier.height(16.dp))

        SectionTitle("이름")
        OutlinedTextField(
            value = charName,
            onValueChange = onNameChange,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("캐릭터 이름 (2~8자)") },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary
            )
        )

        SectionTitle("MBTI")
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            MbtiType.entries.forEach { mbti ->
                FilterChip(
                    selected = selectedMbti == mbti,
                    onClick = { onMbtiSelect(mbti) },
                    label = { Text(mbti.name, style = MaterialTheme.typography.labelSmall) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        SectionTitle("말투")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SpeechStyle.entries.forEach { style ->
                FilterChip(
                    selected = selectedStyle == style,
                    onClick = { onStyleSelect(style) },
                    label = { Text(style.label) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        SectionTitle("관계")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Relationship.entries.forEach { rel ->
                FilterChip(
                    selected = selectedRelationship == rel,
                    onClick = { onRelationshipSelect(rel) },
                    label = { Text(rel.label) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        Spacer(Modifier.height(24.dp))

        Button(
            onClick = onCreate,
            enabled = charName.length >= 2,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("친구 만들기", style = MaterialTheme.typography.titleMedium)
        }

        Spacer(Modifier.height(8.dp))

        OutlinedButton(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("이미지 다시 선택")
        }

        Spacer(Modifier.height(32.dp))
    }
}

@Composable
private fun SectionTitle(title: String) {
    Spacer(Modifier.height(12.dp))
    Text(
        title,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.primary
    )
    Spacer(Modifier.height(6.dp))
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChipGroup(
    options: List<StyleOption>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit
) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        options.forEachIndexed { index, option ->
            FilterChip(
                selected = index == selectedIndex,
                onClick = { onSelect(index) },
                label = { Text(option.label) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    }
}

private fun buildPrompt(
    art: StyleOption,
    hair: StyleOption,
    vibe: StyleOption,
    ethnicity: StyleOption,
    custom: String
): String {
    val base = "A beautiful ${ethnicity.promptEn} character portrait, " +
            "upper body and face visible, ${hair.promptEn}, " +
            "${vibe.promptEn} expression, ${art.promptEn}, " +
            "high quality, detailed face, soft lighting, clean background"
    return if (custom.isNotBlank()) "$base, $custom" else base
}
