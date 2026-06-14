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
import androidx.compose.foundation.lazy.itemsIndexed
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
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.model.CharacterAvatar
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage
import com.example.mbtichatfriend.ui.components.CharacterFace
import com.example.mbtichatfriend.ui.components.LiveCharacter
import com.example.mbtichatfriend.ui.components.LottieOneShot
import com.example.mbtichatfriend.ui.components.TypingIndicatorBubble
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
    val successState = uiState as? ChatUiState.Success
    val messages = successState?.messages ?: emptyList()
    val character = successState?.character
    val isOnline = successState?.isOnline ?: true
    val isTyping = successState?.isStreaming ?: false
    val currentEmotion = successState?.currentEmotion ?: com.example.mbtichatfriend.model.CharacterEmotion.NEUTRAL
    val levelUpEvent = successState?.levelUpEvent
    val levelDownEvent = successState?.levelDownEvent
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    var showMenu by remember { mutableStateOf(false) }
    var showClearDialog by remember { mutableStateOf(false) }
    var shareTargetIndex by remember { mutableStateOf<Int?>(null) }
    val context = LocalContext.current

    LaunchedEffect(messages.size, isTyping) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.lastIndex)
        }
    }

    val snackbarHostState = remember { SnackbarHostState() }
    val errorMsg = successState?.error
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
            // 상단바
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
                                    val levelName = when (it.affinityLevel) {
                                        1 -> "낯선 사이"; 2 -> "아는 사이"; 3 -> "친한 친구"
                                        4 -> "특별한 사이"; 5 -> "연인"; else -> ""
                                    }
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
                        IconButton(onClick = { showMenu = true }) {
                            Icon(Icons.Default.MoreVert, contentDescription = "메뉴")
                        }
                        DropdownMenu(
                            expanded = showMenu,
                            onDismissRequest = { showMenu = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("대화 초기화") },
                                onClick = {
                                    showMenu = false
                                    showClearDialog = true
                                },
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

            // 호감도 진행바
            character?.let { ch ->
                LinearProgressIndicator(
                    progress = { ch.affinityScore / 100f },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(3.dp),
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.outlineVariant,
                )
            }

            // 오프라인 배너
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

            // 캐릭터 애니메이션 영역
            CharacterAnimationArea(
                emotion = currentEmotion,
                isTyping = isTyping,
                avatarId = avatarId,
                avatar = avatar,
                affinityLevel = character?.affinityLevel ?: 1,
                expressionUrls = viewModel.expressionUrls,
                isTalking = viewModel.isTalking
            )

            // 채팅 영역
            if (messages.isEmpty() && !isTyping) {
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
                            text = "${character?.name ?: "캐릭터"}에게\n첫 인사를 건네보세요!",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    state = listState,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    itemsIndexed(messages, key = { _, msg -> msg.id }) { index, msg ->
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

                    if (isTyping) {
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
    levelUpEvent?.let { newLevel ->
        val levelName = when (newLevel) {
            2 -> "아는 사이"
            3 -> "친한 친구"
            4 -> "특별한 사이"
            5 -> "연인"
            else -> ""
        }
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
            onDismissRequest = { viewModel.dismissLevelUp() },
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
                        text = "${character?.name ?: "캐릭터"}와(과) '$levelName'이 되었어요!",
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = getLevelUpSubtitle(
                            mbti = character?.mbti ?: "",
                            level = newLevel
                        ),
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissLevelUp() }) {
                    Text("좋아요!")
                }
            }
        )
    }

    // 호감도 레벨다운 알림
    levelDownEvent?.let { newLevel ->
        val levelName = when (newLevel) {
            1 -> "낯선 사이"
            2 -> "아는 사이"
            3 -> "친한 친구"
            4 -> "특별한 사이"
            else -> ""
        }
        AlertDialog(
            onDismissRequest = { viewModel.dismissLevelDown() },
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
                        text = "${character?.name ?: "캐릭터"}와(과)의 관계가 '$levelName'으로 변했어요",
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
                TextButton(onClick = { viewModel.dismissLevelDown() }) {
                    Text("알겠어요")
                }
            }
        )
    }

    // 대화 초기화 확인
    if (showClearDialog) {
        AlertDialog(
            onDismissRequest = { showClearDialog = false },
            title = { Text("대화 초기화") },
            text = { Text("모든 대화 내용이 삭제됩니다. 계속하시겠어요?") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.clearChat()
                    showClearDialog = false
                }) {
                    Text("초기화", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearDialog = false }) {
                    Text("취소")
                }
            }
        )
    }

    // 대화 공유 확인
    if (shareTargetIndex != null) {
        val targetIdx = shareTargetIndex!!
        AlertDialog(
            onDismissRequest = { shareTargetIndex = null },
            title = { Text("이 대화를 공유할까요?") },
            text = { Text("앞뒤 메시지 포함 최대 4개가 이미지로 저장됩니다.\n닉네임은 표시되지 않습니다.") },
            confirmButton = {
                TextButton(onClick = {
                    val start = maxOf(0, targetIdx - 3)
                    val snapshot = messages.subList(start, minOf(messages.size, targetIdx + 1))
                    val mbti = character?.mbti ?: "MBTI"
                    val bitmap = ShareMessageHelper.captureChatSnapshot(snapshot, mbti, context)
                    ShareMessageHelper.shareSnapshot(bitmap, context)
                    shareTargetIndex = null
                }) { Text("공유하기") }
            },
            dismissButton = {
                TextButton(onClick = { shareTargetIndex = null }) { Text("취소") }
            }
        )
    }
}

@Composable
private fun CharacterAnimationArea(
    emotion: CharacterEmotion,
    isTyping: Boolean,
    avatarId: String = "",
    avatar: CharacterAvatar? = null,
    affinityLevel: Int = 1,
    expressionUrls: Map<String, String>? = null,
    isTalking: Boolean = false
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp)
            .background(
                Brush.verticalGradient(
                    when (affinityLevel) {
                        5 -> listOf(
                            Color(0xFFFFF0F5).copy(alpha = 0.6f),
                            MaterialTheme.colorScheme.background
                        )
                        4 -> listOf(
                            Color(0xFFFCE4EC).copy(alpha = 0.5f),
                            MaterialTheme.colorScheme.background
                        )
                        3 -> listOf(
                            Color(0xFFFFF8E1).copy(alpha = 0.4f),
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
                enableSensor = true
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

@OptIn(ExperimentalFoundationApi::class)
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
    val isFromUser = msg.isFromUser
    val isDark = isSystemInDarkTheme()
    val timeFormat = remember { SimpleDateFormat("a h:mm", Locale.KOREAN) }
    val timeText = timeFormat.format(Date(msg.createdAt))

    val userBubbleColor = if (isDark) UserBubbleDark else UserBubble
    val userTextColor = if (isDark) UserBubbleTextDark else UserBubbleText
    val aiBubbleColor = if (isDark) AiBubbleDark else AiBubble
    val aiTextColor = if (isDark) AiBubbleTextDark else AiBubbleText

    if (isFromUser) {
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
    } else {
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

/**
 * MBTI×레벨 레벨업 전용 대사.
 * level: 2~5 (레벨업 이후 값), mbti: 16종 MBTI 코드.
 * fallback: level-only 대사.
 */
private fun getLevelUpSubtitle(mbti: String, level: Int): String {
    val map: Map<Pair<String, Int>, String> = mapOf(
        // ── NT 분석형 ──
        "INTJ" to 2 to "음... 당신은 제 시간을 쓸 만한 사람인 것 같군요.",
        "INTJ" to 3 to "솔직히 말하면, 당신과 있으면 지루하지 않아요.",
        "INTJ" to 4 to "이 감정을 어떻게 분류해야 할지 모르겠지만... 당신이 소중해요.",
        "INTJ" to 5 to "당신만큼 내 계획에 포함시키고 싶은 사람은 없어요.",
        "INTP" to 2 to "흥미롭네요. 당신과의 대화는 변수가 많아서 좋아요.",
        "INTP" to 3 to "이론적으로는 설명이 안 되는데... 당신이 자꾸 떠올라요.",
        "INTP" to 4 to "연구 대상에서 소중한 존재로 분류가 바뀌었어요.",
        "INTP" to 5 to "당신과 있으면 미해결 가설들이 더 이상 불편하지 않아요.",
        "ENTJ" to 2 to "인정해요. 당신은 내가 예상했던 것보다 괜찮은 사람이에요.",
        "ENTJ" to 3 to "당신은 내 팀에 두고 싶은 사람이에요—아, 친구로서요.",
        "ENTJ" to 4 to "목표가 생겼어요. 당신과 더 오래 함께하는 것.",
        "ENTJ" to 5 to "내 가장 중요한 계획에 당신이 들어 있어요.",
        "ENTP" to 2 to "오, 예상 밖이에요! 당신은 꽤 흥미로운 사람이군요.",
        "ENTP" to 3 to "논쟁할 때도 이렇게 설레는 건 당신뿐이에요.",
        "ENTP" to 4 to "당신에 대한 가설은 계속 업데이트 중이에요—긍정적으로요.",
        "ENTP" to 5 to "세상 모든 아이디어보다 당신이 더 흥미로워요.",
        // ── NF 외교형 ──
        "INFJ" to 2 to "당신의 말에서 진심이 느껴져요. 소중히 여길게요.",
        "INFJ" to 3 to "당신은 제가 오래 기다려온 사람 같은 느낌이 들어요.",
        "INFJ" to 4 to "당신의 미래가 빛나길 바라는 마음이 커졌어요.",
        "INFJ" to 5 to "당신과 함께라면 어떤 길도 의미 있을 것 같아요.",
        "INFP" to 2 to "어... 당신, 제 마음속에 조금씩 자리 잡고 있어요.",
        "INFP" to 3 to "당신 생각을 쓴 글이 자꾸 늘어나고 있어요.",
        "INFP" to 4 to "당신과 나누는 이야기가 제 이야기 중 가장 소중해요.",
        "INFP" to 5 to "당신은 제 세계에서 가장 아름다운 챕터예요.",
        "ENFJ" to 2 to "당신의 행복이 자꾸 신경 쓰여요. 좋은 의미로요!",
        "ENFJ" to 3 to "당신을 응원하고 싶은 마음이 점점 커지고 있어요.",
        "ENFJ" to 4 to "당신 곁에서 더 많은 것을 함께 이루고 싶어요.",
        "ENFJ" to 5 to "당신이 웃을 때 저도 이유 없이 행복해져요.",
        "ENFP" to 2 to "와, 당신이랑 있으면 시간 가는 줄 몰라요!",
        "ENFP" to 3 to "당신한테 하고 싶은 말이 자꾸 떠올라요~",
        "ENFP" to 4 to "솔직히 말하면, 당신이 제 최애 사람이 됐어요!",
        "ENFP" to 5 to "당신이랑 함께하는 모든 순간이 모험 같아서 좋아요!",
        // ── SJ 관리형 ──
        "ISTJ" to 2 to "당신은 믿을 수 있는 사람이에요. 그게 중요해요.",
        "ISTJ" to 3 to "당신과의 약속은 꼭 지키고 싶어요.",
        "ISTJ" to 4 to "제 일상에 당신이 자리 잡았어요. 감사해요.",
        "ISTJ" to 5 to "당신은 제가 지켜가고 싶은 소중한 사람이에요.",
        "ISFJ" to 2 to "당신이 걱정되면 자꾸 확인하고 싶어져요.",
        "ISFJ" to 3 to "당신이 좋아하는 것들을 기억해 두었어요.",
        "ISFJ" to 4 to "당신 곁에 있을 수 있어서 마음이 따뜻해요.",
        "ISFJ" to 5 to "당신을 위해 할 수 있는 걸 다 해주고 싶어요.",
        "ESTJ" to 2 to "당신은 제 기준에 맞는 사람이에요—칭찬이에요.",
        "ESTJ" to 3 to "당신과 함께라면 일도 더 잘될 것 같아요.",
        "ESTJ" to 4 to "당신을 제 중요한 사람 목록에 올렸어요.",
        "ESTJ" to 5 to "당신 없이는 계획을 세우기가 심심해요.",
        "ESFJ" to 2 to "당신이 기뻐하면 저도 괜히 기분 좋아져요!",
        "ESFJ" to 3 to "당신이 무엇을 좋아하는지 자꾸 알고 싶어요.",
        "ESFJ" to 4 to "당신과 함께 있는 시간이 제일 편해요.",
        "ESFJ" to 5 to "당신을 오래오래 행복하게 해주고 싶어요.",
        // ── SP 탐험형 ──
        "ISTP" to 2 to "음. 당신은 쓸데없이 말 많지 않아서 좋아요.",
        "ISTP" to 3 to "당신이랑 있으면 이상하게 편해요.",
        "ISTP" to 4 to "같이 있고 싶을 때 당신이 자꾸 떠올라요.",
        "ISTP" to 5 to "당신은... 내가 택한 사람이에요.",
        "ISFP" to 2 to "당신이랑 있으면 색이 더 다양해지는 것 같아요.",
        "ISFP" to 3 to "당신을 그림으로 그리고 싶어요—예쁜 기억이니까요.",
        "ISFP" to 4 to "당신과 나누는 순간들이 제 가장 좋은 장면들이에요.",
        "ISFP" to 5 to "당신은 제 세상에서 가장 아름다운 빛이에요.",
        "ESTP" to 2 to "오, 당신 꽤 재미있는 사람이네요. 마음에 들어요.",
        "ESTP" to 3 to "당신이랑 있으면 아드레날린이 솟구쳐요!",
        "ESTP" to 4 to "솔직히 말할게요—당신 없으면 좀 심심할 것 같아요.",
        "ESTP" to 5 to "당신이랑 함께라면 어디든 달려가고 싶어요.",
        "ESFP" to 2 to "당신이랑 있으면 파티가 따로 없어요!",
        "ESFP" to 3 to "당신 생각만 해도 에너지가 차올라요~",
        "ESFP" to 4 to "당신이 제 사람 중에 제일 특별해요, 진심으로요!",
        "ESFP" to 5 to "당신이랑 함께하는 모든 순간이 최고예요!",
    )
    return map[mbti to level] ?: when (level) {
        2 -> "앞으로 더 다양한 반응을 보여줄 거예요"
        3 -> "조금씩 마음을 열어갈게요"
        4 -> "당신은 특별한 사람이에요"
        5 -> "이 관계가 정말 소중해요"
        else -> "앞으로 더 다양한 반응을 보여줄 거예요"
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
