package com.example.mbtichatfriend.ui.settings

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.CardGiftcard
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.BuildConfig
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    onYearReport: () -> Unit = {},
    onLanguageSetting: () -> Unit = {},
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val nickname by viewModel.nickname.collectAsState()
    val darkMode by viewModel.darkMode.collectAsState()
    val authProvider by viewModel.authProvider.collectAsState()
    val linkError by viewModel.linkError.collectAsState()
    val referralCode by viewModel.referralCode.collectAsState()
    val referralStats by viewModel.referralStats.collectAsState()
    val referralDeepLink by viewModel.referralDeepLink.collectAsState()
    val referralCtaText = viewModel.referralCtaText
    val redeemState by viewModel.redeemState.collectAsState()
    val deleteAccountState by viewModel.deleteAccountState.collectAsState()
    val context = LocalContext.current
    var showNicknameDialog by remember { mutableStateOf(false) }
    var showLogoutDialog by remember { mutableStateOf(false) }
    var showDeleteAccountDialog by remember { mutableStateOf(false) }
    var showDeleteAccountConfirmDialog by remember { mutableStateOf(false) }
    var inviteCodeInput by remember { mutableStateOf("") }
    var redeemSnackbarMessage by remember { mutableStateOf<String?>(null) }
    var deleteAccountErrorMessage by remember { mutableStateOf<String?>(null) }

    // 리딤 결과를 스낵바로 노출 후 상태 초기화
    LaunchedEffect(redeemState) {
        when (val state = redeemState) {
            is SettingsViewModel.RedeemState.Success -> {
                redeemSnackbarMessage =
                    if (state.bonusDays > 0) "초대 코드 적용 완료! +${state.bonusDays}일 보너스"
                    else "초대 코드가 적용되었습니다."
                inviteCodeInput = ""
                viewModel.clearRedeemState()
            }
            is SettingsViewModel.RedeemState.Error -> {
                redeemSnackbarMessage = state.message
                viewModel.clearRedeemState()
            }
            else -> Unit
        }
    }

    // 계정 삭제 결과 처리
    LaunchedEffect(deleteAccountState) {
        when (val state = deleteAccountState) {
            is SettingsViewModel.DeleteAccountState.Error -> {
                deleteAccountErrorMessage = state.message
                viewModel.clearDeleteAccountState()
            }
            else -> Unit
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .systemBarsPadding()
    ) {
        TopAppBar(
            title = { Text("설정") },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "뒤로가기")
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.background
            )
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // 프로필 섹션 - 아바타 포함
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.4f)
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 유저 아바타
                    androidx.compose.material3.Surface(
                        modifier = Modifier.size(56.dp),
                        shape = androidx.compose.foundation.shape.CircleShape,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
                    ) {
                        androidx.compose.foundation.layout.Box(
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = nickname.take(1).uppercase(),
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = nickname.ifEmpty { "사용자" },
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = when (authProvider) {
                                "google" -> "Google 계정"
                                else -> "비회원"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    IconButton(onClick = { showNicknameDialog = true }) {
                        Icon(
                            Icons.Default.Edit,
                            contentDescription = "닉네임 수정",
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // 계정 섹션
            SectionTitle("계정")
            SettingsItem(
                icon = Icons.Default.AccountCircle,
                title = "로그인 상태",
                subtitle = when (authProvider) {
                    "google" -> "Google 계정으로 로그인됨"
                    "anonymous" -> "비회원 (익명)"
                    else -> "로그인하지 않음"
                }
            )
            if (authProvider != "google") {
                Button(
                    onClick = { viewModel.linkGoogleAccount(context) },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Icon(
                        Icons.Default.Link,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                    Text(
                        text = "  Google 계정 연동",
                        color = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            // 테마 섹션
            SectionTitle("테마")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                ThemeOption(
                    icon = Icons.Default.PhoneAndroid,
                    label = "시스템",
                    isSelected = darkMode == "system",
                    onClick = { viewModel.updateDarkMode("system") },
                    modifier = Modifier.weight(1f)
                )
                ThemeOption(
                    icon = Icons.Default.LightMode,
                    label = "라이트",
                    isSelected = darkMode == "light",
                    onClick = { viewModel.updateDarkMode("light") },
                    modifier = Modifier.weight(1f)
                )
                ThemeOption(
                    icon = Icons.Default.DarkMode,
                    label = "다크",
                    isSelected = darkMode == "dark",
                    onClick = { viewModel.updateDarkMode("dark") },
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(Modifier.height(8.dp))

            // 레퍼럴 섹션 (27차 스프린트 / 30차 A/B)
            SectionTitle(referralCtaText)
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f)
                )
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    // 레퍼럴 통계
                    referralStats?.let { stats ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    text = "${stats.invitedCount}명",
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                Text(
                                    text = "내가 초대한 친구",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    text = "+${stats.rewardDays}일",
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.tertiary
                                )
                                Text(
                                    text = "리워드",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                    }
                    // 초대 코드 표시
                    if (referralCode.isNotEmpty()) {
                        Text(
                            text = "내 초대 코드: $referralCode",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSecondaryContainer
                        )
                        Spacer(Modifier.height(8.dp))
                    }
                    // 공유 버튼들 (V3: 딥링크 URL 우선, 폴백 코드 텍스트)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // 일반 공유 버튼 — 딥링크 URL 우선 공유 (A/B CTA 텍스트 적용, 30차 스프린트)
                        FilledTonalButton(
                            onClick = {
                                viewModel.generateReferralLink { shareContent ->
                                    val intent = Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, shareContent)
                                    }
                                    context.startActivity(Intent.createChooser(intent, referralCtaText))
                                }
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(
                                Icons.Default.Share,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(referralCtaText)
                        }
                        // 카카오톡 공유 버튼 — 딥링크 URL 우선, 미설치 시 일반 공유 폴백
                        OutlinedButton(
                            onClick = {
                                viewModel.generateReferralLink { shareContent ->
                                    val intent = Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, shareContent)
                                        setPackage("com.kakao.talk")
                                    }
                                    runCatching {
                                        context.startActivity(intent)
                                    }.onFailure {
                                        val fallback = Intent(Intent.ACTION_SEND).apply {
                                            type = "text/plain"
                                            putExtra(Intent.EXTRA_TEXT, shareContent)
                                        }
                                        context.startActivity(Intent.createChooser(fallback, "친구 초대"))
                                    }
                                }
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("카카오톡", color = Color(0xFFFFE812))
                        }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // 초대 코드 입력 섹션 (A8 이후 Settings 이동)
            SectionTitle("초대 코드 입력")
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.4f)
                )
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "친구에게 받은 초대 코드를 입력하면 보너스 이용일을 받을 수 있어요.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = inviteCodeInput,
                        onValueChange = { if (it.length <= 16) inviteCodeInput = it.uppercase() },
                        label = { Text("초대 코드") },
                        placeholder = { Text("예: ABC12345") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = MaterialTheme.colorScheme.tertiary
                        ),
                        leadingIcon = {
                            Icon(
                                Icons.Default.CardGiftcard,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.tertiary
                            )
                        },
                        enabled = redeemState !is SettingsViewModel.RedeemState.Loading
                    )
                    Spacer(Modifier.height(10.dp))
                    FilledTonalButton(
                        onClick = { viewModel.redeemInviteCode(inviteCodeInput) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        enabled = inviteCodeInput.trim().isNotEmpty() &&
                                redeemState !is SettingsViewModel.RedeemState.Loading,
                        colors = androidx.compose.material3.ButtonDefaults.filledTonalButtonColors(
                            containerColor = MaterialTheme.colorScheme.tertiaryContainer
                        )
                    ) {
                        if (redeemState is SettingsViewModel.RedeemState.Loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "적용 중...",
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                        } else {
                            Text(
                                "적용하기",
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // 언어 설정 섹션 (36차 스프린트)
            SectionTitle("언어")
            SettingsItem(
                icon = Icons.Default.Language,
                title = "언어 설정",
                subtitle = "한국어 / English",
                onClick = onLanguageSetting
            )

            Spacer(Modifier.height(8.dp))

            // 리포트 섹션 (22차 스프린트)
            SectionTitle("리포트")
            SettingsItem(
                icon = Icons.Default.EmojiEvents,
                title = "2026 나의 대화 리포트",
                subtitle = "올해 나의 대화를 돌아봐요",
                onClick = onYearReport
            )

            Spacer(Modifier.height(8.dp))

            // 앱 정보
            SectionTitle("정보")
            SettingsItem(
                icon = Icons.Default.Info,
                title = "앱 버전",
                subtitle = BuildConfig.VERSION_NAME
            )

            Spacer(Modifier.height(8.dp))

            // 로그아웃
            SettingsItem(
                icon = Icons.AutoMirrored.Filled.Logout,
                title = "로그아웃",
                subtitle = "데이터가 초기화됩니다",
                onClick = { showLogoutDialog = true },
                isDestructive = true
            )

            // 계정 삭제 (A-8)
            SettingsItem(
                icon = Icons.Default.DeleteForever,
                title = "계정 삭제",
                subtitle = "모든 데이터가 영구 삭제됩니다",
                onClick = {
                    if (deleteAccountState !is SettingsViewModel.DeleteAccountState.Loading) {
                        showDeleteAccountDialog = true
                    }
                },
                isDestructive = true
            )

            Spacer(Modifier.height(32.dp))
        }
    }

    // 계정 연동 에러 Snackbar
    linkError?.let { error ->
        Snackbar(
            modifier = Modifier.padding(16.dp),
            action = {
                TextButton(onClick = { viewModel.clearLinkError() }) {
                    Text("확인")
                }
            }
        ) {
            Text(error)
        }
    }

    // 초대 코드 리딤 결과 Snackbar
    redeemSnackbarMessage?.let { msg ->
        Snackbar(
            modifier = Modifier.padding(16.dp),
            action = {
                TextButton(onClick = { redeemSnackbarMessage = null }) {
                    Text("확인")
                }
            }
        ) {
            Text(msg)
        }
    }

    // 계정 삭제 에러 Snackbar
    deleteAccountErrorMessage?.let { msg ->
        Snackbar(
            modifier = Modifier.padding(16.dp),
            action = {
                TextButton(onClick = { deleteAccountErrorMessage = null }) {
                    Text("확인")
                }
            }
        ) {
            Text(msg)
        }
    }

    // 계정 삭제 1단계 확인 다이얼로그
    if (showDeleteAccountDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteAccountDialog = false },
            title = { Text("계정 삭제") },
            text = {
                Text(
                    "계정을 삭제하면 모든 채팅 내역, 캐릭터, 일기가 영구 삭제됩니다.\n" +
                    "이 작업은 되돌릴 수 없습니다."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteAccountDialog = false
                        showDeleteAccountConfirmDialog = true
                    }
                ) {
                    Text("계속", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteAccountDialog = false }) {
                    Text("취소")
                }
            }
        )
    }

    // 계정 삭제 2단계 최종 확인 다이얼로그
    if (showDeleteAccountConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteAccountConfirmDialog = false },
            title = { Text("정말 삭제하시겠어요?") },
            text = {
                Text("'삭제' 버튼을 누르면 계정과 모든 데이터가 즉시 삭제됩니다.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteAccountConfirmDialog = false
                        viewModel.deleteAccount(onSuccess = onLogout)
                    }
                ) {
                    Text("삭제", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteAccountConfirmDialog = false }) {
                    Text("취소")
                }
            }
        )
    }

    // 닉네임 변경 다이얼로그
    if (showNicknameDialog) {
        NicknameEditDialog(
            currentNickname = nickname,
            onDismiss = { showNicknameDialog = false },
            onConfirm = { newNickname ->
                viewModel.updateNickname(newNickname)
                showNicknameDialog = false
            }
        )
    }

    // 로그아웃 확인 다이얼로그
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = { Text("로그아웃") },
            text = { Text("모든 데이터가 초기화됩니다. 정말 로그아웃 하시겠어요?") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showLogoutDialog = false
                        viewModel.logout(onLogout)
                    }
                ) {
                    Text("로그아웃", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text("취소")
                }
            }
        )
    }
}

@Composable
private fun SectionTitle(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(vertical = 4.dp)
    )
}

@Composable
private fun SettingsItem(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: (() -> Unit)? = null,
    isDestructive: Boolean = false
) {
    Card(
        onClick = { onClick?.invoke() },
        enabled = onClick != null,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = if (isDestructive) MaterialTheme.colorScheme.error
                else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    color = if (isDestructive) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun ThemeOption(
    icon: ImageVector,
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) MaterialTheme.colorScheme.primaryContainer
            else MaterialTheme.colorScheme.surface
        ),
        border = if (isSelected) androidx.compose.foundation.BorderStroke(
            2.dp, MaterialTheme.colorScheme.primary
        ) else null
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                icon,
                contentDescription = label,
                tint = if (isSelected) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = if (isSelected) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun NicknameEditDialog(
    currentNickname: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var newNickname by remember { mutableStateOf(currentNickname) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("닉네임 변경") },
        text = {
            OutlinedTextField(
                value = newNickname,
                onValueChange = { if (it.length <= 8) newNickname = it },
                label = { Text("새 닉네임 (2~8자)") },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary
                )
            )
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(newNickname) },
                enabled = newNickname.length in 2..8
            ) {
                Text("변경")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("취소")
            }
        }
    )
}

