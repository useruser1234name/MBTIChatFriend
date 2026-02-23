package com.example.mbtichatfriend.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
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
import androidx.compose.ui.unit.sp
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.ui.components.CharacterFace

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AvatarBuilderSheet(
    initial: AvatarConfig = AvatarConfig(),
    onConfirm: (AvatarConfig) -> Unit
) {
    var config by remember { mutableStateOf(initial) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("캐릭터 꾸미기", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        Spacer(Modifier.height(20.dp))

        // ── 미리보기 ───────────────────────────────────────────
        Surface(
            shape = CircleShape,
            tonalElevation = 4.dp,
            modifier = Modifier.size(120.dp)
        ) {
            CharacterFace(
                avatarId = config.toId(),
                modifier = Modifier.size(120.dp)
            )
        }

        Spacer(Modifier.height(24.dp))
        HorizontalDivider()

        // ── 배경 색상 ──────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("배경 색상")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.BG_COLORS.forEachIndexed { idx, colorLong ->
                ColorDot(
                    color  = Color(colorLong),
                    selected = config.bgColorIndex == idx,
                    onClick  = { config = config.copy(bgColorIndex = idx) }
                )
            }
        }

        // ── 피부 톤 ────────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("피부 톤")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.SKIN_TONES.forEachIndexed { idx, color ->
                ColorDot(
                    color    = color,
                    selected = config.skinTone == idx,
                    onClick  = { config = config.copy(skinTone = idx) }
                )
            }
        }

        // ── 헤어 스타일 ────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("헤어 스타일")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.HAIR_STYLE_NAMES.forEachIndexed { idx, name ->
                StyleChip(
                    label    = name,
                    selected = config.hairStyle == idx,
                    onClick  = { config = config.copy(hairStyle = idx) }
                )
            }
        }

        // ── 헤어 컬러 ──────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("헤어 컬러")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.HAIR_COLORS.forEachIndexed { idx, color ->
                ColorDot(
                    color    = color,
                    selected = config.hairColor == idx,
                    onClick  = { config = config.copy(hairColor = idx) }
                )
            }
        }

        // ── 눈 스타일 ──────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("눈 스타일")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.EYE_STYLE_NAMES.forEachIndexed { idx, name ->
                StyleChip(
                    label    = name,
                    selected = config.eyeStyle == idx,
                    onClick  = { config = config.copy(eyeStyle = idx) }
                )
            }
        }

        // ── 볼 터치 ────────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("볼 터치", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Switch(
                checked  = config.blushEnabled,
                onCheckedChange = { config = config.copy(blushEnabled = it) }
            )
        }

        // ── 악세서리 ───────────────────────────────────────────
        Spacer(Modifier.height(16.dp))
        SectionLabel("악세서리")
        Spacer(Modifier.height(8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AvatarConfig.ACCESSORY_NAMES.forEachIndexed { idx, name ->
                StyleChip(
                    label    = name,
                    selected = config.accessory == idx,
                    onClick  = { config = config.copy(accessory = idx) }
                )
            }
        }

        Spacer(Modifier.height(28.dp))

        Button(
            onClick = { onConfirm(config) },
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("완성!", style = MaterialTheme.typography.titleMedium)
        }

        Spacer(Modifier.height(16.dp))
    }
}

// ── 공통 소형 컴포넌트 ────────────────────────────────────

@Composable
private fun SectionLabel(text: String) {
    Text(
        text  = text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun ColorDot(color: Color, selected: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(36.dp)
            .clip(CircleShape)
            .background(color)
            .then(
                if (selected) Modifier.border(3.dp, MaterialTheme.colorScheme.primary, CircleShape)
                else Modifier.border(1.dp, Color.White.copy(alpha = 0.6f), CircleShape)
            )
            .clickable(onClick = onClick)
    )
}

@Composable
private fun StyleChip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected  = selected,
        onClick   = onClick,
        label     = { Text(label, style = MaterialTheme.typography.labelMedium) },
        colors    = FilterChipDefaults.filterChipColors(
            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
            selectedLabelColor     = MaterialTheme.colorScheme.onPrimaryContainer
        )
    )
}
