package com.example.mbtichatfriend.ui.profile

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationScreen(
    onNavigateBack: () -> Unit,
    onNavigateToCommunityPost: (Long) -> Unit = {},
    onNavigateToReferral: () -> Unit = {},
    viewModel: NotificationViewModel = hiltViewModel(),
) {
    val notifications by viewModel.notifications.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(Unit) { viewModel.loadAndMarkRead() }

    // deep_link 파싱 후 해당 화면으로 이동
    fun handleDeepLink(deepLink: String?) {
        if (deepLink.isNullOrEmpty()) return
        val uri = Uri.parse(deepLink)
        when {
            // mbtichat://community/{post_id}
            uri.scheme == "mbtichat" && uri.host == "community" -> {
                val postId = uri.lastPathSegment?.toLongOrNull() ?: return
                onNavigateToCommunityPost(postId)
            }
            // mbtichat://settings/referral
            uri.scheme == "mbtichat" && uri.host == "settings" && uri.path == "/referral" -> {
                onNavigateToReferral()
            }
            // 기타 딥링크: 시스템 인텐트로 처리
            else -> {
                runCatching {
                    context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("알림") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로")
                    }
                }
            )
        }
    ) { padding ->
        if (isLoading) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (notifications.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text("새 알림이 없어요", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(Modifier.padding(padding)) {
                items(notifications) { notif ->
                    ListItem(
                        modifier = Modifier.clickable(
                            enabled = !notif.deepLink.isNullOrEmpty()
                        ) {
                            handleDeepLink(notif.deepLink)
                        },
                        headlineContent = {
                            Text(
                                notif.title,
                                fontWeight = if (!notif.isRead) FontWeight.Bold else FontWeight.Normal
                            )
                        },
                        supportingContent = {
                            Text(notif.body, style = MaterialTheme.typography.bodySmall)
                        },
                        trailingContent = if (!notif.isRead) ({
                            Surface(
                                shape = MaterialTheme.shapes.small,
                                color = MaterialTheme.colorScheme.primary
                            ) {
                                Box(Modifier.size(8.dp))
                            }
                        }) else null,
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}
