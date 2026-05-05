@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.mbtichatfriend.ui.community

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.app.ShareCompat
import androidx.hilt.navigation.compose.hiltViewModel
import com.example.mbtichatfriend.data.remote.CommunityComment

@Composable
fun PostDetailScreen(
    postId: Long,
    onNavigateBack: () -> Unit,
    viewModel: PostDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    var commentInput by remember { mutableStateOf("") }
    val maxLength = 150
    val context = LocalContext.current

    LaunchedEffect(postId) { viewModel.loadPost(postId) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("게시글") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로")
                    }
                },
                actions = {
                    if (uiState is PostDetailUiState.Success) {
                        val successState = uiState as PostDetailUiState.Success
                        IconButton(onClick = {
                            val shareUrl = "https://mbtichat.page.link/community/${postId}"
                            val shareText = "[${successState.post.mbti}] ${successState.post.content.take(50)}...\n${shareUrl}"
                            ShareCompat.IntentBuilder(context)
                                .setType("text/plain")
                                .setText(shareText)
                                .setChooserTitle("게시글 공유")
                                .startChooser()
                        }) {
                            Icon(Icons.Default.Share, "공유")
                        }
                    }
                }
            )
        },
        bottomBar = {
            BottomAppBar(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = commentInput,
                        onValueChange = { if (it.length <= maxLength) commentInput = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("댓글을 남겨보세요 (${maxLength}자)") },
                        singleLine = true,
                        trailingIcon = {
                            Text(
                                "${commentInput.length}/$maxLength",
                                style = MaterialTheme.typography.labelSmall,
                                modifier = Modifier.padding(end = 8.dp),
                            )
                        }
                    )
                    Spacer(Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            if (commentInput.isNotBlank()) {
                                viewModel.createComment(commentInput)
                                commentInput = ""
                            }
                        },
                        enabled = commentInput.isNotBlank(),
                    ) {
                        Icon(Icons.Default.Send, "전송")
                    }
                }
            }
        }
    ) { padding ->
        when (val state = uiState) {
            is PostDetailUiState.Loading -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            is PostDetailUiState.Success -> {
                LazyColumn(
                    modifier = Modifier.padding(padding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    // 게시글
                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    SuggestionChip(onClick = {}, label = { Text(state.post.mbti) })
                                    Text(
                                        state.post.anonymousName,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Spacer(Modifier.height(8.dp))
                                Text(state.post.content, style = MaterialTheme.typography.bodyMedium)
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    "공감 ${state.post.empathyCount}  댓글 ${state.comments.size}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    // 댓글 헤더
                    if (state.comments.isNotEmpty()) {
                        item {
                            Text(
                                "댓글 ${state.comments.size}",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(vertical = 4.dp),
                            )
                        }
                    }
                    // 댓글 목록
                    items(state.comments, key = { it.id }) { comment ->
                        CommentItem(comment = comment)
                    }
                }
            }
            is PostDetailUiState.Error -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    Text(state.message)
                }
            }
        }
    }
}

@Composable
private fun CommentItem(comment: CommunityComment) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SuggestionChip(onClick = {}, label = { Text(comment.mbti, style = MaterialTheme.typography.labelSmall) })
        Column(modifier = Modifier.weight(1f)) {
            Text(
                comment.anonymousName,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(comment.content, style = MaterialTheme.typography.bodySmall)
        }
    }
}
