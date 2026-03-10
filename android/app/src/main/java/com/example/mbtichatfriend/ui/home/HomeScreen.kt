package com.example.mbtichatfriend.ui.home

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Brush
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.ui.components.CharacterFace
import androidx.compose.material3.rememberModalBottomSheetState
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onCharacterClick: (Long) -> Unit,
    onCreateCharacter: () -> Unit,
    onSettings: () -> Unit,
    onGallery: () -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel()
) {
    val characters by viewModel.characters.collectAsState()
    val nickname by viewModel.nickname.collectAsState()
    val lastMessages by viewModel.lastMessages.collectAsState()

    var deleteTarget by remember { mutableStateOf<CharacterEntity?>(null) }
    var showImageGenerator by remember { mutableStateOf(false) }
    val chatApi = viewModel.chatApi
    val imageGeneratorSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    // 삭제 확인 다이얼로그
    deleteTarget?.let { character ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("캐릭터 삭제") },
            text = {
                Text("'${character.name}'을(를) 삭제하시겠어요?\n대화 기록도 모두 삭제됩니다.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.deleteCharacter(character.id)
                        deleteTarget = null
                    },
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("삭제")
                }
            },
            dismissButton = {
                TextButton(onClick = { deleteTarget = null }) {
                    Text("취소")
                }
            }
        )
    }

    Scaffold(
        modifier = Modifier.systemBarsPadding(),
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "안녕, $nickname!",
                            style = MaterialTheme.typography.titleLarge
                        )
                        Text(
                            text = "누구와 대화할까요?",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "설정")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = onCreateCharacter,
                containerColor = MaterialTheme.colorScheme.primary,
                shape = CircleShape
            ) {
                Icon(
                    Icons.Default.Add,
                    contentDescription = "캐릭터 추가",
                    tint = MaterialTheme.colorScheme.onPrimary
                )
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        if (characters.isEmpty()) {
            EmptyState(
                onGallery = onGallery,
                onCreateCharacter = onCreateCharacter,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
            )
        } else {
            // 최근 대화 순으로 정렬: 마지막 메시지가 있는 캐릭터 우선, 그 다음 생성일 역순
            val sorted = characters.sortedByDescending { ch ->
                lastMessages[ch.id]?.timestamp ?: ch.createdAt
            }

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    GalleryBannerCard(onClick = onGallery)
                }
                item {
                    ImageGeneratorBannerCard(onClick = { showImageGenerator = true })
                }
                items(sorted, key = { it.id }) { character ->
                    CharacterCard(
                        character = character,
                        lastMessage = lastMessages[character.id],
                        onClick = { onCharacterClick(character.id) },
                        onLongClick = { deleteTarget = character }
                    )
                }
            }
        }
    }

    if (showImageGenerator) {
        ImageGeneratorSheet(
            sheetState = imageGeneratorSheetState,
            chatApi = chatApi,
            onDismiss = { showImageGenerator = false },
            onCharacterCreated = { name, mbti, speechStyle, relationship, avatarId, revisedPrompt ->
                viewModel.createCharacter(name, mbti, speechStyle, relationship, avatarId, revisedPrompt) { characterId ->
                    showImageGenerator = false
                    onCharacterClick(characterId)
                }
            }
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun CharacterCard(
    character: CharacterEntity,
    lastMessage: LastMessageInfo?,
    onClick: () -> Unit,
    onLongClick: () -> Unit
) {
    val avatarId = character.avatarId
    val affinityColor by animateColorAsState(
        targetValue = when (character.affinityLevel) {
            1 -> Color(0xFFB0B0C0)
            2 -> Color(0xFFB5E8D5)
            3 -> Color(0xFFFFF3B0)
            4 -> Color(0xFFFFB5C2)
            5 -> Color(0xFFC9B1FF)
            else -> Color(0xFFB0B0C0)
        },
        label = "affinityColor"
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .combinedClickable(
                onClick = onClick,
                onLongClick = onLongClick
            ),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 캐릭터 아바타
            CharacterFace(
                avatarId = avatarId,
                modifier = Modifier
                    .size(60.dp)
                    .clip(CircleShape),
                legacyFontSize = 32f
            )

            Spacer(Modifier.width(16.dp))

            // 캐릭터 정보
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = character.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = character.mbti,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier
                            .background(
                                MaterialTheme.colorScheme.primaryContainer,
                                RoundedCornerShape(4.dp)
                            )
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                    Spacer(Modifier.width(6.dp))
                    // 호감도 레벨 표시
                    val levelTag = when (character.affinityLevel) {
                        2 -> "Lv.2"
                        3 -> "Lv.3"
                        4 -> "Lv.4"
                        5 -> "Lv.5"
                        else -> null
                    }
                    levelTag?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.labelSmall,
                            color = affinityColor,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .background(
                                    affinityColor.copy(alpha = 0.15f),
                                    RoundedCornerShape(4.dp)
                                )
                                .padding(horizontal = 5.dp, vertical = 1.dp)
                        )
                    }
                }

                Spacer(Modifier.height(4.dp))

                // 최근 대화 미리보기 또는 호감도
                if (lastMessage != null) {
                    Text(
                        text = lastMessage.text,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = formatRelativeTime(lastMessage.timestamp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline
                    )
                } else {
                    val levelName = when (character.affinityLevel) {
                        1 -> "낯선 사이"
                        2 -> "아는 사이"
                        3 -> "친한 친구"
                        4 -> "특별한 사이"
                        5 -> "연인"
                        else -> "낯선 사이"
                    }
                    Text(
                        text = "$levelName | ${character.affinityScore}/100",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Spacer(Modifier.height(4.dp))

                LinearProgressIndicator(
                    progress = { character.affinityScore / 100f },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(4.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = affinityColor,
                    trackColor = MaterialTheme.colorScheme.outlineVariant,
                )
            }
        }
    }
}

private fun formatRelativeTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    val minutes = diff / 60_000
    val hours = diff / 3_600_000
    val days = diff / 86_400_000

    return when {
        minutes < 1 -> "방금 전"
        minutes < 60 -> "${minutes}분 전"
        hours < 24 -> "${hours}시간 전"
        days < 7 -> "${days}일 전"
        else -> SimpleDateFormat("M월 d일", Locale.KOREAN).format(Date(timestamp))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GalleryBannerCard(onClick: () -> Unit) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "MBTI 캐릭터 갤러리",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
                Text(
                    text = "16가지 MBTI 친구 둘러보기",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.75f)
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onPrimaryContainer
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ImageGeneratorBannerCard(onClick: () -> Unit) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer
        )
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "이상형 만들기",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onTertiaryContainer
                )
                Text(
                    text = "AI로 나만의 이상형 캐릭터 생성",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onTertiaryContainer.copy(alpha = 0.75f)
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onTertiaryContainer
            )
        }
    }
}

@Composable
private fun EmptyState(onGallery: () -> Unit = {}, onCreateCharacter: () -> Unit = {}, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.padding(horizontal = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Lottie 빈 채팅 애니메이션
        com.example.mbtichatfriend.ui.components.LottieOneShot(
            assetName = "lottie/empty_chat.json",
            modifier = Modifier.size(160.dp),
            iterations = Int.MAX_VALUE
        )

        Spacer(Modifier.height(20.dp))

        Text(
            text = "아직 친구가 없어요",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = "16가지 MBTI 성격의 캐릭터 중\n마음에 드는 친구를 골라보세요!",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Spacer(Modifier.height(28.dp))
        androidx.compose.material3.Button(
            onClick = onGallery,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text("갤러리에서 캐릭터 고르기", style = MaterialTheme.typography.titleSmall)
        }
        Spacer(Modifier.height(12.dp))
        FilledTonalButton(
            onClick = onCreateCharacter,
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("+ 직접 만들기", style = MaterialTheme.typography.titleSmall)
        }
    }
}
