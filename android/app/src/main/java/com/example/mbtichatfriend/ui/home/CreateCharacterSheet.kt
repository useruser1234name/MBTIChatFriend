package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.model.MbtiType
import com.example.mbtichatfriend.model.Relationship
import com.example.mbtichatfriend.model.SpeechStyle
import com.example.mbtichatfriend.ui.components.CharacterFace

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun CreateCharacterSheet(
    onDismiss: () -> Unit,
    onCreate: (name: String, mbti: String, speechStyle: String, relationship: String, avatarId: String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var selectedMbti by remember { mutableStateOf(MbtiType.ENFP) }
    var selectedStyle by remember { mutableStateOf(SpeechStyle.CASUAL) }
    var selectedRelationship by remember { mutableStateOf(Relationship.FRIEND) }
    var avatarConfig by remember { mutableStateOf(AvatarConfig()) }
    var showAvatarBuilder by remember { mutableStateOf(false) }

    // 아바타 빌더 바텀시트
    if (showAvatarBuilder) {
        ModalBottomSheet(
            onDismissRequest = { showAvatarBuilder = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ) {
            AvatarBuilderSheet(
                initial   = avatarConfig,
                onConfirm = { newConfig ->
                    avatarConfig = newConfig
                    showAvatarBuilder = false
                }
            )
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            text = "새 친구 만들기",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        Spacer(Modifier.height(24.dp))

        // ── 아바타 미리보기 + 꾸미기 버튼 ──────────────────────
        Text("캐릭터", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(Color(avatarConfig.bgColor).copy(alpha = 0.5f))
            ) {
                CharacterFace(
                    avatarId = avatarConfig.toId(),
                    modifier = Modifier.size(80.dp)
                )
            }
            OutlinedButton(
                onClick = { showAvatarBuilder = true },
                shape   = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp))
                Text("꾸미기")
            }
        }

        Spacer(Modifier.height(16.dp))

        // 이름 입력
        Text("이름", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        OutlinedTextField(
            value = name,
            onValueChange = { if (it.length <= 8) name = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("캐릭터 이름 (2~8자)") },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline
            )
        )

        Spacer(Modifier.height(16.dp))

        // MBTI 선택
        Text("MBTI", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            MbtiType.entries.forEach { mbti ->
                FilterChip(
                    selected = selectedMbti == mbti,
                    onClick = { selectedMbti = mbti },
                    label = { Text(mbti.name, style = MaterialTheme.typography.labelSmall) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        // 말투
        Text("말투", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SpeechStyle.entries.forEach { style ->
                FilterChip(
                    selected = selectedStyle == style,
                    onClick = { selectedStyle = style },
                    label = { Text(style.label) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        // 관계
        Text("관계", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Relationship.entries.forEach { rel ->
                FilterChip(
                    selected = selectedRelationship == rel,
                    onClick = { selectedRelationship = rel },
                    label = { Text(rel.label) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                )
            }
        }

        Spacer(Modifier.height(24.dp))

        // 생성 버튼
        Button(
            onClick = {
                if (name.length >= 2) {
                    onCreate(name, selectedMbti.name, selectedStyle.name, selectedRelationship.name, avatarConfig.toId())
                }
            },
            enabled = name.length >= 2,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("친구 만들기", style = MaterialTheme.typography.titleMedium)
        }

        Spacer(Modifier.height(16.dp))
    }
}
