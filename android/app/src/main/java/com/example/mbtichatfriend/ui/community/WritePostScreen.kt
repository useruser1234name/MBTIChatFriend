@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.mbtichatfriend.ui.community

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun WritePostScreen(
    onNavigateBack: () -> Unit,
    viewModel: CommunityViewModel = hiltViewModel(),
) {
    var content by remember { mutableStateOf("") }
    val maxLength = 300
    val userId by viewModel.userId.collectAsState()
    val userMbti by viewModel.userMbti.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("고민 쓰기") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, "뒤로")
                    }
                },
                actions = {
                    TextButton(
                        onClick = {
                            if (content.isNotBlank()) {
                                viewModel.createPost(userId, userMbti, content) {
                                    onNavigateBack()
                                }
                            }
                        },
                        enabled = content.isNotBlank(),
                    ) { Text("등록") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp),
        ) {
            SuggestionChip(onClick = {}, label = { Text(userMbti) })
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = content,
                onValueChange = { if (it.length <= maxLength) content = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp),
                placeholder = { Text("$userMbti 라면 공감할 고민을 자유롭게 남겨보세요.") },
                maxLines = 10,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "${content.length} / $maxLength",
                style = MaterialTheme.typography.labelSmall,
                color = if (content.length >= maxLength) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}
