package com.example.mbtichatfriend.ui.diary

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

// ── 32차 스프린트: 사용자 감정 태그 + 직접 입력 다이어리 화면 ────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiaryEntryScreen(
    viewModel: DiaryEntryViewModel = hiltViewModel(),
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    // 저장 성공 시 자동 뒤로 이동
    LaunchedEffect(uiState.isSaved) {
        if (uiState.isSaved) onBack()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("오늘의 다이어리") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "뒤로"
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // 감정 태그 선택
            LazyRow(modifier = Modifier.padding(16.dp)) {
                items(listOf("\uD83D\uDE0A 기쁨", "\uD83D\uDE14 슬픔", "\uD83D\uDE30 불안", "\uD83D\uDE24 화남", "\uD83E\uDD14 복잡")) { tag ->
                    FilterChip(
                        selected = uiState.selectedTags.contains(tag),
                        onClick = { viewModel.toggleTag(tag) },
                        label = { Text(tag) },
                        modifier = Modifier.padding(end = 8.dp)
                    )
                }
            }

            // 일기 입력
            OutlinedTextField(
                value = uiState.content,
                onValueChange = viewModel::updateContent,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(16.dp),
                placeholder = { Text("오늘 하루 어떠셨나요?") },
                maxLines = 20
            )

            Button(
                onClick = viewModel::saveDiary,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                enabled = uiState.content.isNotBlank() && !uiState.isSaving
            ) {
                Text(if (uiState.isSaving) "저장 중..." else "저장하기")
            }
        }
    }
}
