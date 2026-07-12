@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.mbtichatfriend.ui.community

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.app.ShareCompat
import androidx.hilt.navigation.compose.hiltViewModel

private val MBTI_FILTER_CHIPS = listOf(
    null to "전체",
    "ENFP" to "ENFP", "INFP" to "INFP", "INTJ" to "INTJ",
    "INFJ" to "INFJ", "ENTP" to "ENTP", "ISFJ" to "ISFJ",
    "ISFP" to "ISFP", "ESTJ" to "ESTJ", "INTP" to "INTP",
    "ENTJ" to "ENTJ", "ESFP" to "ESFP", "ESTP" to "ESTP",
)

private val GUIDELINE_LINES = listOf(
    "1. 서로를 존중하는 따뜻한 언어를 사용해요.",
    "2. 개인정보(이름, 연락처 등)를 공유하지 않아요.",
    "3. 불쾌하거나 부적절한 게시글은 신고해 주세요.",
)

@Composable
fun CommunityScreen(
    onNavigateToWrite: () -> Unit,
    onNavigateToDetail: (Long) -> Unit = {},
    viewModel: CommunityViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val userId by viewModel.userId.collectAsState()
    val guidelineShown by viewModel.guidelineShown.collectAsState()
    val context = LocalContext.current

    var showGuidelineDialog by remember { mutableStateOf(false) }

    // 가이드라인 상세 다이얼로그
    if (showGuidelineDialog) {
        AlertDialog(
            onDismissRequest = { showGuidelineDialog = false },
            title = { Text("안전한 고민 공간 가이드라인") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    GUIDELINE_LINES.forEach { line ->
                        Text(line, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showGuidelineDialog = false }) {
                    Text("확인")
                }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("커뮤니티") })
        },
        floatingActionButton = {
            // U1: MaterialTheme.shapes.large가 AppShapes 배선으로 16dp→20dp 바뀌므로
            // FAB 모양(현상) 유지를 위해 기존 M3 기본값(large=16dp)을 명시적으로 고정.
            FloatingActionButton(onClick = onNavigateToWrite, shape = RoundedCornerShape(16.dp)) {
                Icon(Icons.Default.Add, "글 쓰기")
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding)) {
            // MBTI 칩 필터
            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(MBTI_FILTER_CHIPS) { (mbti, label) ->
                    val selected = when (uiState) {
                        is CommunityUiState.Success -> (uiState as CommunityUiState.Success).selectedMbti == mbti
                        else -> mbti == null
                    }
                    FilterChip(
                        selected = selected,
                        onClick = { viewModel.filterByMbti(mbti) },
                        label = { Text(label) },
                    )
                }
            }

            when (val state = uiState) {
                is CommunityUiState.Loading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                is CommunityUiState.Success -> {
                    if (state.posts.isEmpty()) {
                        // 가이드라인 배너 (게시글 없을 때도 최초 1회 표시)
                        if (!guidelineShown) {
                            GuidelineBanner(
                                onClick = {
                                    showGuidelineDialog = true
                                    viewModel.markGuidelineShown()
                                },
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                            )
                        }
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("아직 게시글이 없어요", style = MaterialTheme.typography.bodyLarge)
                                Spacer(Modifier.height(8.dp))
                                Text("첫 글을 남겨보세요!", style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(16.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            // 안전 가이드라인 고정 배너 - 최초 1회만 표시
                            if (!guidelineShown) {
                                item {
                                    GuidelineBanner(
                                        onClick = {
                                            showGuidelineDialog = true
                                            viewModel.markGuidelineShown()
                                        },
                                    )
                                }
                            }
                            // 고정 공지 아이템 (29차 스프린트)
                            if (state.pinnedPosts.isNotEmpty()) {
                                items(state.pinnedPosts, key = { "pinned_${it.id}" }) { pinnedPost ->
                                    PinnedPostCard(post = pinnedPost)
                                }
                            }
                            items(state.posts, key = { it.id }) { post ->
                                PostCard(
                                    post = post,
                                    onEmpathyClick = { viewModel.toggleEmpathy(post.id, userId) },
                                    onShareClick = {
                                        val shareUrl = "https://mbtichat.page.link/community/${post.id}"
                                        val shareText = "[${post.mbti}] ${post.content.take(50)}...\n${shareUrl}"
                                        ShareCompat.IntentBuilder(context)
                                            .setType("text/plain")
                                            .setText(shareText)
                                            .setChooserTitle("게시글 공유")
                                            .startChooser()
                                    },
                                    onCardClick = { onNavigateToDetail(post.id) },
                                    onReport = { reason -> viewModel.reportPost(post.id, reason) },
                                )
                            }
                        }
                    }
                }
                is CommunityUiState.Error -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(state.message)
                    }
                }
            }
        }
    }
}

// 고정 공지 카드 (29차 스프린트)
@Composable
private fun PinnedPostCard(
    post: CommunityPostUi,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.6f),
        ),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    imageVector = Icons.Default.PushPin,
                    contentDescription = "고정 공지",
                    modifier = Modifier.size(16.dp),
                    tint = MaterialTheme.colorScheme.tertiary,
                )
                Text(
                    text = "공지",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.tertiary,
                )
                if (post.mbti.isNotEmpty()) {
                    SuggestionChip(
                        onClick = {},
                        label = { Text(post.mbti, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                text = post.content,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onTertiaryContainer,
            )
        }
    }
}

@Composable
private fun GuidelineBanner(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "💬 안전한 고민 공간 가이드라인",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "보기",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}
