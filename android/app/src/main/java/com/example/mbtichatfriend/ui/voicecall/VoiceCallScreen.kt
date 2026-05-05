package com.example.mbtichatfriend.ui.voicecall

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.mbtichatfriend.model.AvatarConfig
import com.example.mbtichatfriend.model.CharacterAvatar
import com.example.mbtichatfriend.ui.components.CharacterFace
import com.example.mbtichatfriend.ui.components.EmotionLottieBackground
import com.example.mbtichatfriend.model.CharacterEmotion
import android.Manifest

@Composable
fun VoiceCallScreen(
    onBack: () -> Unit,
    viewModel: VoiceCallViewModel = hiltViewModel()
) {
    val character by viewModel.character.collectAsState()
    val callState = viewModel.callState
    val currentEmotion = viewModel.currentEmotion
    val characterSubtitle = viewModel.characterSubtitle
    val userSpeechText by viewModel.userSpeechText.collectAsState()
    val levelUpEvent = viewModel.levelUpEvent
    val errorMessage = viewModel.errorMessage

    val avatarId      = character?.avatarId ?: ""
    val affinityLevel = character?.affinityLevel ?: 1

    // 배경 그라디언트 색 (아바타 컬러 기반) - 부드러운 전환
    val baseColor = Color(AvatarConfig.bgColorLong(avatarId))

    val bgAlpha by animateFloatAsState(
        targetValue = when (callState) {
            VoiceCallState.SPEAKING -> 0.55f
            VoiceCallState.LISTENING -> 0.4f
            VoiceCallState.PROCESSING -> 0.3f
            else -> 0.25f
        },
        animationSpec = tween(600),
        label = "bgAlpha"
    )

    val bgGradient = when (callState) {
        VoiceCallState.SPEAKING -> listOf(
            baseColor.copy(alpha = bgAlpha),
            baseColor.copy(alpha = bgAlpha * 0.45f),
            Color(0xFF1A1A2E)
        )
        VoiceCallState.LISTENING -> listOf(
            Color(0xFF1565C0).copy(alpha = bgAlpha),
            Color(0xFF0D47A1).copy(alpha = bgAlpha * 0.5f),
            Color(0xFF1A1A2E)
        )
        VoiceCallState.PROCESSING -> listOf(
            Color(0xFF6A1B9A).copy(alpha = bgAlpha),
            Color(0xFF4A148C).copy(alpha = bgAlpha * 0.5f),
            Color(0xFF1A1A2E)
        )
        else -> listOf(
            baseColor.copy(alpha = bgAlpha),
            Color(0xFF1A1A2E).copy(alpha = 0.8f),
            Color(0xFF1A1A2E)
        )
    }

    // 마이크 권한 요청
    var permissionGranted by remember { mutableStateOf(false) }
    var showPermissionRationale by remember { mutableStateOf(false) }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        permissionGranted = granted
        if (!granted) showPermissionRationale = true
    }

    LaunchedEffect(Unit) {
        permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }

    // 에러 자동 클리어
    LaunchedEffect(errorMessage) {
        if (errorMessage != null) {
            kotlinx.coroutines.delay(3000)
            viewModel.dismissError()
        }
    }

    // 레벨업 다이얼로그
    if (levelUpEvent != null) {
        val lvl = levelUpEvent!!
        AlertDialog(
            onDismissRequest = { viewModel.dismissLevelUp() },
            title = { Text("관계가 깊어졌어요!") },
            text = { Text("${character?.name}와(과)의 호감도가 올랐어요\n레벨 $lvl 달성!") },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissLevelUp() }) { Text("좋아요!") }
            }
        )
    }

    // 권한 안내 다이얼로그
    if (showPermissionRationale) {
        AlertDialog(
            onDismissRequest = { showPermissionRationale = false; onBack() },
            title = { Text("마이크 권한 필요") },
            text = { Text("음성 대화를 하려면 마이크 권한이 필요해요.\n설정에서 허용해주세요.") },
            confirmButton = {
                TextButton(onClick = { showPermissionRationale = false; onBack() }) { Text("확인") }
            }
        )
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(bgGradient))
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // ── 상단 바 ───────────────────────────────────────
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                val stateIndicatorColor by animateColorAsState(
                    targetValue = when (callState) {
                        VoiceCallState.LISTENING -> Color(0xFF4FC3F7)
                        VoiceCallState.SPEAKING -> Color(0xFF81C784)
                        VoiceCallState.PROCESSING -> Color(0xFFCE93D8)
                        else -> Color.White.copy(alpha = 0.7f)
                    },
                    animationSpec = tween(400),
                    label = "stateColor"
                )
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = stateIndicatorColor.copy(alpha = 0.2f)
                ) {
                    Text(
                        text = callStateLabel(callState),
                        style = MaterialTheme.typography.labelMedium,
                        color = stateIndicatorColor,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }
                Text(
                    text = character?.name ?: "",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
                Text(
                    text = affinityLabel(affinityLevel),
                    fontSize = 20.sp
                )
            }

            Spacer(Modifier.height(12.dp))

            // ── 캐릭터 애니메이션 영역 ───────────────────────
            VoiceCharacterArea(
                emotion = currentEmotion,
                avatarId = avatarId,
                affinityLevel = affinityLevel,
                isSpeaking = callState == VoiceCallState.SPEAKING,
                modifier = Modifier.weight(1f)
            )

            Spacer(Modifier.height(8.dp))

            // ── 자막 영역 ────────────────────────────────────
            SubtitleArea(
                characterName = character?.name ?: "",
                characterSubtitle = characterSubtitle,
                userSpeechText = userSpeechText,
                callState = callState,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp)
            )

            Spacer(Modifier.height(28.dp))

            // ── 에러 메시지 ──────────────────────────────────
            AnimatedVisibility(
                visible = errorMessage != null,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color.Red.copy(alpha = 0.25f),
                    modifier = Modifier.padding(horizontal = 20.dp)
                ) {
                    Text(
                        text = errorMessage ?: "",
                        color = Color.White,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        textAlign = TextAlign.Center
                    )
                }
                Spacer(Modifier.height(12.dp))
            }

            Spacer(Modifier.height(8.dp))

            // ── 컨트롤 버튼 ──────────────────────────────────
            VoiceControlBar(
                callState = callState,
                permissionGranted = permissionGranted,
                onMicClick = {
                    when (callState) {
                        VoiceCallState.IDLE -> viewModel.startListening()
                        VoiceCallState.LISTENING -> viewModel.stopListening()
                        else -> {}
                    }
                },
                onEndCall = {
                    viewModel.endCall()
                    onBack()
                }
            )

            Spacer(Modifier.height(32.dp))
        }
    }
}

// ── 캐릭터 애니메이션 ────────────────────────────────────────

@Composable
private fun VoiceCharacterArea(
    emotion: CharacterEmotion,
    avatarId: String,
    affinityLevel: Int,
    isSpeaking: Boolean,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "voice_char")

    // 말할 때 약간 강조되는 bounce
    val bounceY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = if (isSpeaking) -18f else -10f,
        animationSpec = infiniteRepeatable(
            tween(if (isSpeaking) 800 else 1400),
            RepeatMode.Reverse
        ),
        label = "bounce"
    )

    val emotionScale by animateFloatAsState(
        targetValue = when (emotion) {
            CharacterEmotion.HAPPY  -> 1.15f
            CharacterEmotion.LOVE   -> 1.2f
            CharacterEmotion.ANGRY  -> 1.1f
            CharacterEmotion.SURPRISED -> 1.25f
            else -> 1.0f
        },
        animationSpec = spring(stiffness = Spring.StiffnessLow),
        label = "scale"
    )

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.offset(y = bounceY.dp)
        ) {
            // 감정 이펙트 이모지
            EmotionEffectRow(emotion)

            Spacer(Modifier.height(4.dp))

            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier.scale(emotionScale)
            ) {
                EmotionLottieBackground(
                    emotion = emotion,
                    modifier = Modifier.size(160.dp)
                )
                if (avatarId.startsWith("v2:")) {
                    CharacterFace(avatarId = avatarId, modifier = Modifier.size(90.dp))
                } else {
                    Text(
                        text = CharacterAvatar.fromId(avatarId).emoji,
                        fontSize = 90.sp
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            // 말하는 중 표시
            AnimatedVisibility(visible = isSpeaking) {
                SpeakingWaveRow()
            }
        }
    }
}

@Composable
private fun EmotionEffectRow(emotion: CharacterEmotion) {
    // 감정 이펙트는 Lottie 배경으로 표현
    Spacer(Modifier.height(24.dp))
}

/** 음성 파형 애니메이션 바 */
@Composable
private fun SpeakingWaveRow() {
    val infiniteTransition = rememberInfiniteTransition(label = "wave")
    val bars = listOf(0.3f, 0.6f, 1f, 0.8f, 0.5f, 0.9f, 0.4f)

    Row(
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.height(24.dp)
    ) {
        bars.forEachIndexed { index, baseHeight ->
            val scale by infiniteTransition.animateFloat(
                initialValue = 0.3f,
                targetValue = baseHeight,
                animationSpec = infiniteRepeatable(
                    tween(300 + index * 80, easing = LinearEasing),
                    RepeatMode.Reverse
                ),
                label = "bar$index"
            )
            Box(
                modifier = Modifier
                    .size(width = 4.dp, height = (20 * scale).dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(Color.White.copy(alpha = 0.8f))
            )
        }
    }
}

// ── 자막 영역 ────────────────────────────────────────────────

@Composable
private fun SubtitleArea(
    characterName: String,
    characterSubtitle: String,
    userSpeechText: String,
    callState: VoiceCallState,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // 캐릭터 자막
        if (characterSubtitle.isNotEmpty()) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = Color.Black.copy(alpha = 0.55f),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = characterName,
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.6f)
                    )
                    Spacer(Modifier.height(4.dp))
                    TypewriterText(
                        text = characterSubtitle,
                        style = MaterialTheme.typography.bodyLarge,
                        color = Color.White,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        // 사용자 음성 자막
        val userText = when (callState) {
            VoiceCallState.LISTENING  -> userSpeechText.ifEmpty { "듣는 중..." }
            VoiceCallState.PROCESSING -> userSpeechText
            else -> ""
        }
        AnimatedVisibility(visible = userText.isNotEmpty(), enter = fadeIn(), exit = fadeOut()) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = Color.White.copy(alpha = 0.15f),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = userText,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.85f),
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                    textAlign = TextAlign.End
                )
            }
        }

        // PROCESSING 상태 안내
        AnimatedVisibility(
            visible = callState == VoiceCallState.PROCESSING,
            enter = fadeIn(), exit = fadeOut()
        ) {
            Text(
                text = "생각하는 중...",
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.5f),
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center
            )
        }
    }
}

/** 한 글자씩 타이핑되는 효과 */
@Composable
private fun TypewriterText(
    text: String,
    style: androidx.compose.ui.text.TextStyle,
    color: Color,
    fontWeight: FontWeight
) {
    var displayed by remember(text) { mutableStateOf("") }

    LaunchedEffect(text) {
        displayed = ""
        for (char in text) {
            displayed += char
            kotlinx.coroutines.delay(28)
        }
    }

    Text(
        text = displayed,
        style = style,
        color = color,
        fontWeight = fontWeight
    )
}

// ── 컨트롤 바 ────────────────────────────────────────────────

@Composable
private fun VoiceControlBar(
    callState: VoiceCallState,
    permissionGranted: Boolean,
    onMicClick: () -> Unit,
    onEndCall: () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "mic_pulse")
    val micPulse by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.18f,
        animationSpec = infiniteRepeatable(tween(600), RepeatMode.Reverse),
        label = "pulse"
    )

    val isMicActive = callState == VoiceCallState.LISTENING
    val isBusy = callState == VoiceCallState.PROCESSING || callState == VoiceCallState.SPEAKING

    Row(
        horizontalArrangement = Arrangement.spacedBy(40.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 마이크 버튼
        Box(
            modifier = Modifier
                .size(80.dp)
                .scale(if (isMicActive) micPulse else 1f),
            contentAlignment = Alignment.Center
        ) {
            // 펄스 링 (리스닝 중)
            if (isMicActive) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(CircleShape)
                        .background(Color(0xFF1565C0).copy(alpha = 0.3f))
                )
            }
            IconButton(
                onClick = onMicClick,
                enabled = !isBusy && permissionGranted,
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(
                        when {
                            isMicActive -> Color(0xFF1565C0)
                            isBusy      -> Color.Gray.copy(alpha = 0.4f)
                            else        -> Color.White.copy(alpha = 0.15f)
                        }
                    )
            ) {
                Icon(
                    imageVector = if (isMicActive) Icons.Default.MicOff else Icons.Default.Mic,
                    contentDescription = if (isMicActive) "녹음 중지" else "말하기",
                    tint = Color.White,
                    modifier = Modifier.size(32.dp)
                )
            }
        }

        // 통화 종료 버튼
        IconButton(
            onClick = onEndCall,
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(Color(0xFFE53935))
        ) {
            Icon(
                imageVector = Icons.Default.CallEnd,
                contentDescription = "통화 종료",
                tint = Color.White,
                modifier = Modifier.size(28.dp)
            )
        }
    }

    Spacer(Modifier.height(12.dp))
    Text(
        text = when (callState) {
            VoiceCallState.IDLE       -> if (permissionGranted) "마이크 버튼을 눌러 말해보세요" else "마이크 권한이 필요해요"
            VoiceCallState.LISTENING  -> "말씀하세요... (다시 누르면 중지)"
            VoiceCallState.PROCESSING -> "답변을 생각하는 중이에요"
            VoiceCallState.SPEAKING   -> "말하는 중..."
        },
        style = MaterialTheme.typography.bodySmall,
        color = Color.White.copy(alpha = 0.55f),
        textAlign = TextAlign.Center
    )
}

// ── 헬퍼 ─────────────────────────────────────────────────────

private fun callStateLabel(state: VoiceCallState) = when (state) {
    VoiceCallState.IDLE       -> "대기 중"
    VoiceCallState.LISTENING  -> "녹음 중"
    VoiceCallState.PROCESSING -> "처리 중"
    VoiceCallState.SPEAKING   -> "재생 중"
}

private fun affinityLabel(level: Int) = when (level) {
    1 -> "Lv.1"; 2 -> "Lv.2"; 3 -> "Lv.3"; 4 -> "Lv.4"; 5 -> "Lv.5"; else -> "Lv.1"
}
