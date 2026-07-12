package com.example.mbtichatfriend.ui.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.SuggestionChip
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.model.CharacterAvatar
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage
import com.example.mbtichatfriend.ui.components.CharacterFace
import com.example.mbtichatfriend.ui.components.LiveCharacter
import com.example.mbtichatfriend.ui.components.LottieOneShot
import com.example.mbtichatfriend.ui.components.motionProfileForMbti
import com.example.mbtichatfriend.ui.components.TypingIndicatorBubble
import com.example.mbtichatfriend.ui.components.affinityLevelName
import com.example.mbtichatfriend.ui.components.ConfirmDialog
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.ui.zIndex
import androidx.compose.foundation.BorderStroke
import com.example.mbtichatfriend.ui.theme.AiBubble
import com.example.mbtichatfriend.ui.theme.AiBubbleDark
import com.example.mbtichatfriend.ui.theme.AiBubbleText
import com.example.mbtichatfriend.ui.theme.AiBubbleTextDark
import com.example.mbtichatfriend.ui.theme.AccentRed
import com.example.mbtichatfriend.ui.theme.UserBubble
import com.example.mbtichatfriend.ui.theme.UserBubbleDark
import com.example.mbtichatfriend.ui.theme.UserBubbleText
import com.example.mbtichatfriend.ui.theme.UserBubbleTextDark
import com.example.mbtichatfriend.ui.theme.*
import androidx.compose.ui.platform.LocalContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ChatScreen(
    onBack: () -> Unit,
    onProfile: (Long) -> Unit,
    onVoiceCall: (Long) -> Unit = {},
    onNavigateToCompatibility: () -> Unit = {},
    viewModel: ChatViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val messages = (uiState as? ChatUiState.Success)?.messages ?: emptyList()
    val character = (uiState as? ChatUiState.Success)?.character
    val isOnline = (uiState as? ChatUiState.Success)?.isOnline ?: true
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    var showMenu by remember { mutableStateOf(false) }
    var showClearDialog by remember { mutableStateOf(false) }
    var shareTargetIndex by remember { mutableStateOf<Int?>(null) }
    val context = LocalContext.current

    LaunchedEffect(messages.size, viewModel.isTyping) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.lastIndex)
        }
    }

    val snackbarHostState = remember { SnackbarHostState() }
    val errorMsg = viewModel.errorMessage
    LaunchedEffect(errorMsg) {
        errorMsg?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.dismissError()
        }
    }

    val avatarId = character?.avatarId ?: ""
    val avatar = character?.let { CharacterAvatar.fromId(it.avatarId) }  // legacy background color

    // 화면 가시성 추적
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            viewModel.isScreenVisible = event == Lifecycle.Event.ON_RESUME ||
                    event == Lifecycle.Event.ON_START
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.isScreenVisible = false
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .systemBarsPadding()
        ) {
            ChatTopBar(
                character = character,
                avatar = avatar,
                isTyping = viewModel.isTyping,
                currentEmotion = viewModel.currentEmotion,
                showMenu = showMenu,
                onBack = onBack,
                onProfile = onProfile,
                onVoiceCall = onVoiceCall,
                onNavigateToCompatibility = onNavigateToCompatibility,
                onMenuExpandedChange = { showMenu = it },
                onClearChatRequest = {
                    showMenu = false
                    showClearDialog = true
                }
            )

            AffinityProgressBar(affinityScore = character?.affinityScore)

            OfflineBanner(isOnline = isOnline)

            // 캐릭터 애니메이션 영역
            CharacterAnimationArea(
                emotion = viewModel.currentEmotion,
                isTyping = viewModel.isTyping,
                avatarId = avatarId,
                avatar = avatar,
                affinityLevel = character?.affinityLevel ?: 1,
                expressionUrls = viewModel.expressionUrls,
                isTalking = viewModel.isTalking,
                mbti = character?.mbti ?: ""
            )

            // 채팅 영역
            if (messages.isEmpty() && !viewModel.isTyping) {
                EmptyChatPlaceholder(characterName = character?.name)
            } else {
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    state = listState,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    items(messages, key = { it.id }) { msg ->
                        val index = messages.indexOf(msg)
                        AnimatedVisibility(
                            visible = true,
                            enter = fadeIn(tween(300)) + slideInVertically(
                                initialOffsetY = { 40 },
                                animationSpec = spring(stiffness = Spring.StiffnessLow)
                            )
                        ) {
                            MessageBubble(
                                msg = msg,
                                avatarId = avatarId,
                                avatar = avatar,
                                onRetry = { messageId -> viewModel.retrySend(messageId) },
                                feedback = viewModel.feedbackMap.value[msg.id],
                                onFeedback = { messageId, type -> viewModel.submitFeedback(messageId, type) },
                                onLongPress = { shareTargetIndex = index }
                            )
                        }
                    }

                    if (viewModel.isTyping) {
                        item { TypingBubble(avatarId, avatar) }
                    }
                }
            }

            // 입력 바 (대화 스타터 chip 포함, 26차 스프린트)
            ChatInputBar(
                input = input,
                onInputChange = { input = it },
                onSend = {
                    viewModel.send(input)
                    input = ""
                },
                onChipClick = { chipText ->
                    viewModel.send(chipText)
                }
            )
        }

        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.Center)
                .padding(horizontal = 24.dp)
        )
    }

    // 호감도 레벨업 축하 팝업 + Lottie 오버레이
    viewModel.levelUpEvent?.let { newLevel ->
        LevelUpDialog(
            newLevel = newLevel,
            characterName = character?.name,
            onDismiss = { viewModel.dismissLevelUp() }
        )
    }

    // 호감도 레벨다운 알림
    viewModel.levelDownEvent?.let { newLevel ->
        LevelDownDialog(
            newLevel = newLevel,
            characterName = character?.name,
            onDismiss = { viewModel.dismissLevelDown() }
        )
    }

    // 대화 초기화 확인
    if (showClearDialog) {
        ConfirmDialog(
            title = "대화 초기화",
            text = "모든 대화 내용이 삭제됩니다. 계속하시겠어요?",
            confirmLabel = "초기화",
            dismissLabel = "취소",
            confirmColor = MaterialTheme.colorScheme.error,
            onConfirm = {
                viewModel.clearChat()
                showClearDialog = false
            },
            onDismiss = { showClearDialog = false }
        )
    }

    // 대화 공유 확인
    if (shareTargetIndex != null) {
        val targetIdx = shareTargetIndex!!
        ConfirmDialog(
            title = "이 대화를 공유할까요?",
            text = "앞뒤 메시지 포함 최대 4개가 이미지로 저장됩니다.\n닉네임은 표시되지 않습니다.",
            confirmLabel = "공유하기",
            dismissLabel = "취소",
            onConfirm = {
                val start = maxOf(0, targetIdx - 3)
                val snapshot = messages.subList(start, minOf(messages.size, targetIdx + 1))
                val mbti = character?.mbti ?: "MBTI"
                val bitmap = ShareMessageHelper.captureChatSnapshot(snapshot, mbti, context)
                ShareMessageHelper.shareSnapshot(bitmap, context)
                shareTargetIndex = null
            },
            onDismiss = { shareTargetIndex = null }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatTopBar(
    character: CharacterEntity?,
    avatar: CharacterAvatar?,
    isTyping: Boolean,
    currentEmotion: CharacterEmotion,
    showMenu: Boolean,
    onBack: () -> Unit,
    onProfile: (Long) -> Unit,
    onVoiceCall: (Long) -> Unit,
    onNavigateToCompatibility: () -> Unit,
    onMenuExpandedChange: (Boolean) -> Unit,
    onClearChatRequest: () -> Unit,
) {
    TopAppBar(
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.clickable { character?.let { onProfile(it.id) } }
            ) {
                if (avatar != null) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color(avatar.colorHex).copy(alpha = 0.3f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(avatar.emoji, fontSize = 20.sp)
                    }
                }
                Spacer(Modifier.width(10.dp))
                Column {
                    Text(
                        text = character?.name ?: "...",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    if (isTyping) {
                        Text(
                            text = "입력 중...",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    } else {
                        character?.let {
                            val levelName = affinityLevelName(it.affinityLevel)
                            Text(
                                text = "${emotionEmoji(currentEmotion)} $levelName",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }
        },
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로가기")
            }
        },
        actions = {
            IconButton(onClick = { character?.let { onVoiceCall(it.id) } }) {
                Icon(Icons.Default.Phone, contentDescription = "음성 대화")
            }
            IconButton(onClick = onNavigateToCompatibility) {
                Icon(Icons.Default.Favorite, contentDescription = "궁합 보기")
            }
            IconButton(onClick = { character?.let { onProfile(it.id) } }) {
                Icon(Icons.Default.Person, contentDescription = "프로필")
            }
            Box {
                IconButton(onClick = { onMenuExpandedChange(true) }) {
                    Icon(Icons.Default.MoreVert, contentDescription = "메뉴")
                }
                DropdownMenu(
                    expanded = showMenu,
                    onDismissRequest = { onMenuExpandedChange(false) }
                ) {
                    DropdownMenuItem(
                        text = { Text("대화 초기화") },
                        onClick = onClearChatRequest,
                        leadingIcon = {
                            Icon(Icons.Default.DeleteOutline, contentDescription = null)
                        }
                    )
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    )
}

@Composable
private fun AffinityProgressBar(affinityScore: Int?) {
    if (affinityScore != null) {
        LinearProgressIndicator(
            progress = { affinityScore / 100f },
            modifier = Modifier
                .fillMaxWidth()
                .height(3.dp),
            color = MaterialTheme.colorScheme.primary,
            trackColor = MaterialTheme.colorScheme.outlineVariant,
        )
    }
}

@Composable
private fun OfflineBanner(isOnline: Boolean) {
    AnimatedVisibility(visible = !isOnline) {
        Surface(
            color = AccentRed.copy(alpha = 0.9f),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = "오프라인 - 메시지는 연결 시 자동 전송됩니다",
                style = MaterialTheme.typography.labelMedium,
                color = Color.White,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 6.dp)
            )
        }
    }
}

@Composable
private fun ColumnScope.EmptyChatPlaceholder(characterName: String?) {
    Box(
        modifier = Modifier
            .weight(1f)
            .fillMaxWidth(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            LottieOneShot(
                assetName = "lottie/empty_chat.json",
                modifier = Modifier.size(120.dp),
                iterations = Int.MAX_VALUE
            )
            Spacer(Modifier.height(12.dp))
            Text(
                text = "${characterName ?: "캐릭터"}에게\n첫 인사를 건네보세요!",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun LevelUpDialog(
    newLevel: Int,
    characterName: String?,
    onDismiss: () -> Unit,
) {
    val levelName = affinityLevelName(newLevel)
    val levelLabel = when (newLevel) {
        2 -> "Lv.2"; 3 -> "Lv.3"; 4 -> "Lv.4"; 5 -> "Lv.5"
        else -> ""
    }
    // 축하 Lottie 오버레이
    Box(modifier = Modifier.fillMaxSize().zIndex(10f)) {
        LottieOneShot(
            assetName = "lottie/levelup.json",
            modifier = Modifier.fillMaxSize(),
            onFinished = { /* 애니메이션 종료 후 자동 사라짐 */ }
        )
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                Text(levelLabel, fontSize = 32.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(8.dp))
                Text("관계가 발전했어요!", fontWeight = FontWeight.Bold)
            }
        },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "${characterName ?: "캐릭터"}와(과) '$levelName'이 되었어요!",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "앞으로 더 다양한 반응을 보여줄 거예요",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("좋아요!")
            }
        }
    )
}

@Composable
private fun LevelDownDialog(
    newLevel: Int,
    characterName: String?,
    onDismiss: () -> Unit,
) {
    val levelName = affinityLevelName(newLevel)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "...",
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(8.dp))
                Text("관계가 변했어요...", fontWeight = FontWeight.Bold)
            }
        },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "${characterName ?: "캐릭터"}와(과)의 관계가 '$levelName'으로 변했어요",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "다정하게 대화하면 다시 가까워질 수 있어요",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("알겠어요")
            }
        }
    )
}

@Composable
private fun CharacterAnimationArea(
    emotion: CharacterEmotion,
    isTyping: Boolean,
    avatarId: String = "",
    avatar: CharacterAvatar? = null,
    affinityLevel: Int = 1,
    expressionUrls: Map<String, String>? = null,
    isTalking: Boolean = false,
    mbti: String = ""
) {
    // C7: MBTI별 유휴 모션 프로파일 (mbti가 비어있거나 인식 불가면 기존 동작과 동일한 기본값)
    val motionProfile = remember(mbti) { motionProfileForMbti(mbti) }
    // U2: 다크모드에서 라이트 파스텔이 그대로 밝게 워시되던 문제 — 감정 버블과 동일한 isDark 분기 패턴 적용
    val isDarkStage = isSystemInDarkTheme()
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp)
            .background(
                Brush.verticalGradient(
                    when (affinityLevel) {
                        5 -> listOf(
                            (if (isDarkStage) AffinityBgLv5Dark else AffinityBgLv5).copy(alpha = 0.6f),
                            MaterialTheme.colorScheme.background
                        )
                        4 -> listOf(
                            (if (isDarkStage) AffinityBgLv4Dark else AffinityBgLv4).copy(alpha = 0.5f),
                            MaterialTheme.colorScheme.background
                        )
                        3 -> listOf(
                            (if (isDarkStage) AffinityBgLv3Dark else AffinityBgLv3).copy(alpha = 0.4f),
                            MaterialTheme.colorScheme.background
                        )
                        else -> listOf(
                            MaterialTheme.colorScheme.surface,
                            MaterialTheme.colorScheme.background
                        )
                    }
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 감정 이펙트 (Lottie 애니메이션으로 표현)

            LiveCharacter(
                emotion = emotion,
                characterSize = 100.dp,
                enableSensor = true,
                motionProfile = motionProfile
            ) {
                if (avatarId.startsWith("img:") || avatarId.startsWith("v2:")) {
                    CharacterFace(
                        avatarId = avatarId,
                        modifier = Modifier.size(if (avatarId.startsWith("img:")) 100.dp else 80.dp),
                        emotion = emotion,
                        expressionUrls = expressionUrls,
                        isTalking = isTalking
                    )
                } else {
                    Text(
                        text = avatar?.emoji ?: emotionEmoji(emotion),
                        fontSize = 56.sp
                    )
                }
            }

            Spacer(Modifier.height(4.dp))

            if (isTyping) {
                Text(
                    text = "생각하는 중...",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                Text(
                    text = emotion.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun MessageBubble(
    msg: ChatMessage,
    avatarId: String = "",
    avatar: CharacterAvatar? = null,
    onRetry: ((Long) -> Unit)? = null,
    feedback: String? = null,
    onFeedback: ((Long, String) -> Unit)? = null,
    onLongPress: (() -> Unit)? = null
) {
    if (msg.isFromUser) {
        UserMessageBubble(
            msg = msg,
            onRetry = onRetry,
            onLongPress = onLongPress
        )
    } else {
        AiMessageBubble(
            msg = msg,
            avatarId = avatarId,
            avatar = avatar,
            feedback = feedback,
            onFeedback = onFeedback,
            onLongPress = onLongPress
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun UserMessageBubble(
    msg: ChatMessage,
    onRetry: ((Long) -> Unit)? = null,
    onLongPress: (() -> Unit)? = null
) {
    val isDark = isSystemInDarkTheme()
    val timeFormat = remember { SimpleDateFormat("a h:mm", Locale.KOREAN) }
    val timeText = timeFormat.format(Date(msg.createdAt))

    val userBubbleColor = if (isDark) UserBubbleDark else UserBubble
    val userTextColor = if (isDark) UserBubbleTextDark else UserBubbleText

    // 유저 메시지: 오른쪽 정렬
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.End
    ) {
        Surface(
            shape = RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp),
            color = if (msg.sendStatus == "FAILED") userBubbleColor.copy(alpha = 0.6f) else userBubbleColor,
            shadowElevation = 1.dp,
            modifier = Modifier
                .widthIn(max = 280.dp)
                .combinedClickable(
                    onClick = {},
                    onLongClick = { onLongPress?.invoke() }
                )
        ) {
            Text(
                text = msg.text,
                style = MaterialTheme.typography.bodyLarge,
                color = userTextColor,
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
            )
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
        ) {
            when (msg.sendStatus) {
                "PENDING" -> {
                    val infiniteTransition = rememberInfiniteTransition(label = "pending")
                    val alpha by infiniteTransition.animateFloat(
                        initialValue = 0.3f,
                        targetValue = 1f,
                        animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse),
                        label = "pendingAlpha"
                    )
                    Text(
                        text = "전송 대기 중",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha),
                    )
                }
                "FAILED" -> {
                    Icon(
                        Icons.Default.ErrorOutline,
                        contentDescription = "전송 실패",
                        tint = AccentRed,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        text = "전송 실패",
                        style = MaterialTheme.typography.labelSmall,
                        color = AccentRed
                    )
                    if (onRetry != null) {
                        Spacer(Modifier.width(6.dp))
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = AccentRed.copy(alpha = 0.1f),
                            modifier = Modifier.clickable { onRetry(msg.id) }
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            ) {
                                Icon(
                                    Icons.Default.Refresh,
                                    contentDescription = "재전송",
                                    tint = AccentRed,
                                    modifier = Modifier.size(12.dp)
                                )
                                Spacer(Modifier.width(2.dp))
                                Text(
                                    text = "재전송",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = AccentRed
                                )
                            }
                        }
                    }
                }
                else -> {
                    Text(
                        text = timeText,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun AiMessageBubble(
    msg: ChatMessage,
    avatarId: String = "",
    avatar: CharacterAvatar? = null,
    feedback: String? = null,
    onFeedback: ((Long, String) -> Unit)? = null,
    onLongPress: (() -> Unit)? = null
) {
    val isDark = isSystemInDarkTheme()
    val timeFormat = remember { SimpleDateFormat("a h:mm", Locale.KOREAN) }
    val timeText = timeFormat.format(Date(msg.createdAt))
    val aiBubbleColor = if (isDark) AiBubbleDark else AiBubble
    val aiTextColor = if (isDark) AiBubbleTextDark else AiBubbleText

    // AI 메시지: 감정 표정 아바타 + 말풍선
    val emotion = msg.emotion
    val emotionBubbleColor = if (emotion != null && emotion != CharacterEmotion.NEUTRAL) {
        if (isDark) emotionBubbleDark(emotion) else emotionBubbleLight(emotion)
    } else {
        aiBubbleColor
    }
    val emotionBorder = if (emotion != null && emotion != CharacterEmotion.NEUTRAL) {
        BorderStroke(1.5.dp, emotionBorderColor(emotion).copy(alpha = 0.5f))
    } else {
        null
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        // 캐릭터 아바타 (감정 이모지 or Compose 캐릭터)
        if (avatarId.startsWith("v2:")) {
            CharacterFace(
                avatarId = avatarId,
                modifier = Modifier
                    .padding(top = 2.dp)
                    .size(36.dp)
                    .clip(CircleShape),
                emotion = emotion ?: CharacterEmotion.NEUTRAL
            )
        } else {
            Box(
                modifier = Modifier
                    .padding(top = 2.dp)
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(
                        if (emotion != null && emotion != CharacterEmotion.NEUTRAL) {
                            emotionBorderColor(emotion).copy(alpha = 0.15f)
                        } else {
                            avatar?.let { Color(it.colorHex).copy(alpha = 0.3f) }
                                ?: MaterialTheme.colorScheme.primaryContainer
                        }
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = emotionEmoji(emotion ?: CharacterEmotion.NEUTRAL),
                    fontSize = 22.sp
                )
            }
        }

        Spacer(Modifier.width(8.dp))

        Column {
            Surface(
                shape = RoundedCornerShape(20.dp, 20.dp, 20.dp, 4.dp),
                color = emotionBubbleColor,
                border = emotionBorder,
                tonalElevation = 1.dp,
                shadowElevation = 1.dp,
                modifier = Modifier
                    .widthIn(max = 260.dp)
                    .combinedClickable(
                        onClick = {},
                        onLongClick = { onLongPress?.invoke() }
                    )
            ) {
                Text(
                    text = msg.text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = aiTextColor,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
            ) {
                Text(
                    text = timeText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                )

                // 피드백 아이콘 (500ms 후 fade-in)
                if (onFeedback != null) {
                    var visible by remember { mutableStateOf(false) }
                    LaunchedEffect(Unit) {
                        kotlinx.coroutines.delay(500)
                        visible = true
                    }
                    AnimatedVisibility(
                        visible = visible,
                        enter = fadeIn(tween(300))
                    ) {
                        Row(
                            modifier = Modifier.padding(start = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(2.dp)
                        ) {
                            // 좋아요
                            IconButton(
                                onClick = { onFeedback(msg.id, "thumbs_up") },
                                enabled = feedback == null,
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    Icons.Default.ThumbUp,
                                    contentDescription = "좋아요",
                                    modifier = Modifier.size(14.dp).graphicsLayer {
                                        alpha = when (feedback) {
                                            "thumbs_up" -> 1f
                                            "thumbs_down" -> 0.3f
                                            else -> 0.5f
                                        }
                                    },
                                    tint = if (feedback == "thumbs_up") MaterialTheme.colorScheme.primary
                                           else MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            // 아쉬워요
                            IconButton(
                                onClick = { onFeedback(msg.id, "thumbs_down") },
                                enabled = feedback == null,
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    Icons.Default.ThumbDown,
                                    contentDescription = "아쉬워요",
                                    modifier = Modifier.size(14.dp).graphicsLayer {
                                        alpha = when (feedback) {
                                            "thumbs_down" -> 1f
                                            "thumbs_up" -> 0.3f
                                            else -> 0.5f
                                        }
                                    },
                                    tint = if (feedback == "thumbs_down") MaterialTheme.colorScheme.error
                                           else MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TypingBubble(avatarId: String = "", avatar: CharacterAvatar? = null) {
    val infiniteTransition = rememberInfiniteTransition(label = "typing")
    val isDark = isSystemInDarkTheme()

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        // 캐릭터 아바타 (생각 중)
        if (avatarId.startsWith("v2:")) {
            CharacterFace(
                avatarId = avatarId,
                modifier = Modifier.padding(top = 2.dp).size(36.dp).clip(CircleShape)
            )
        } else {
            Box(
                modifier = Modifier
                    .padding(top = 2.dp)
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(
                        avatar?.let { Color(it.colorHex).copy(alpha = 0.3f) }
                            ?: MaterialTheme.colorScheme.primaryContainer
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.MoreHoriz,
                    contentDescription = null,
                    modifier = Modifier.size(22.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Spacer(Modifier.width(8.dp))

        // 타이핑 버블
        Surface(
            shape = RoundedCornerShape(20.dp, 20.dp, 20.dp, 4.dp),
            color = if (isDark) AiBubbleDark else AiBubble,
            tonalElevation = 1.dp,
            shadowElevation = 1.dp
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(5.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp)
            ) {
                repeat(3) { index ->
                    val offsetY by infiniteTransition.animateFloat(
                        initialValue = 0f,
                        targetValue = -6f,
                        animationSpec = infiniteRepeatable(
                            tween(400, delayMillis = index * 150),
                            RepeatMode.Reverse
                        ),
                        label = "dot$index"
                    )
                    Box(
                        modifier = Modifier
                            .offset(y = offsetY.dp)
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.6f))
                    )
                }
            }
        }
    }
}

@Composable
private fun ChatInputBar(
    input: String,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    starterChips: List<String> = emptyList(),
    onChipClick: (String) -> Unit = {},
) {
    val sendEnabled = input.isNotBlank()
    val sendScale by animateFloatAsState(
        targetValue = if (sendEnabled) 1f else 0.85f,
        label = "sendScale"
    )

    Surface(
        tonalElevation = 3.dp,
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 4.dp
    ) {
        Column {
            // 대화 스타터 chip — 항상 노출 (26차 스프린트)
            val chips = starterChips.ifEmpty {
                listOf("오늘 하루 어땠어?", "나 고민이 있어", "재미있는 얘기 해줘!")
            }
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(horizontal = 4.dp)
            ) {
                items(chips) { chipText ->
                    SuggestionChip(
                        onClick = { onChipClick(chipText) },
                        label = {
                            Text(
                                text = chipText,
                                style = MaterialTheme.typography.labelMedium,
                                maxLines = 1
                            )
                        },
                        shape = RoundedCornerShape(20.dp),
                    )
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = onInputChange,
                    modifier = Modifier.weight(1f),
                    placeholder = {
                        Text(
                            "메시지를 입력하세요",
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    },
                    singleLine = false,
                    maxLines = 4,
                    shape = RoundedCornerShape(24.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = MaterialTheme.colorScheme.primary,
                        unfocusedBorderColor = Color.Transparent,
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { if (sendEnabled) onSend() })
                )
                Spacer(Modifier.width(8.dp))
                IconButton(
                    onClick = { if (sendEnabled) onSend() },
                    enabled = sendEnabled,
                    modifier = Modifier
                        .size(48.dp)
                        .graphicsLayer { scaleX = sendScale; scaleY = sendScale }
                        .clip(CircleShape)
                        .background(
                            if (sendEnabled) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        contentDescription = "전송",
                        tint = if (sendEnabled) MaterialTheme.colorScheme.onPrimary
                        else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }
    }
}

private fun emotionEmoji(emotion: CharacterEmotion): String = when (emotion) {
    CharacterEmotion.NEUTRAL -> "~"
    CharacterEmotion.HAPPY -> "^^"
    CharacterEmotion.SHY -> "//"
    CharacterEmotion.SAD -> "ㅠ"
    CharacterEmotion.ANGRY -> "!!"
    CharacterEmotion.SURPRISED -> "?!"
    CharacterEmotion.LOVE -> "<3"
    CharacterEmotion.PLAYFUL -> ":P"
    CharacterEmotion.WORRIED -> "..."
    CharacterEmotion.TOUCHED -> "T_T"
}

private fun emotionBubbleLight(emotion: CharacterEmotion): Color = when (emotion) {
    CharacterEmotion.LOVE -> EmotionLoveBubble
    CharacterEmotion.HAPPY -> EmotionHappyBubble
    CharacterEmotion.ANGRY -> EmotionAngryBubble
    CharacterEmotion.SAD -> EmotionSadBubble
    CharacterEmotion.SHY -> EmotionShyBubble
    CharacterEmotion.SURPRISED -> EmotionSurprisedBubble
    CharacterEmotion.PLAYFUL -> EmotionPlayfulBubble
    CharacterEmotion.WORRIED -> EmotionWorriedBubble
    CharacterEmotion.TOUCHED -> EmotionTouchedBubble
    else -> AiBubble
}

private fun emotionBubbleDark(emotion: CharacterEmotion): Color = when (emotion) {
    CharacterEmotion.LOVE -> EmotionLoveBubbleDark
    CharacterEmotion.HAPPY -> EmotionHappyBubbleDark
    CharacterEmotion.ANGRY -> EmotionAngryBubbleDark
    CharacterEmotion.SAD -> EmotionSadBubbleDark
    CharacterEmotion.SHY -> EmotionShyBubbleDark
    CharacterEmotion.SURPRISED -> EmotionSurprisedBubbleDark
    CharacterEmotion.PLAYFUL -> EmotionPlayfulBubbleDark
    CharacterEmotion.WORRIED -> EmotionWorriedBubbleDark
    CharacterEmotion.TOUCHED -> EmotionTouchedBubbleDark
    else -> AiBubbleDark
}

private fun emotionBorderColor(emotion: CharacterEmotion): Color = when (emotion) {
    CharacterEmotion.LOVE -> EmotionLoveBorder
    CharacterEmotion.HAPPY -> EmotionHappyBorder
    CharacterEmotion.ANGRY -> EmotionAngryBorder
    CharacterEmotion.SAD -> EmotionSadBorder
    CharacterEmotion.SHY -> EmotionShyBorder
    CharacterEmotion.PLAYFUL -> EmotionPlayfulBorder
    CharacterEmotion.WORRIED -> EmotionWorriedBorder
    CharacterEmotion.TOUCHED -> EmotionTouchedBorder
    else -> Color.Transparent
}
