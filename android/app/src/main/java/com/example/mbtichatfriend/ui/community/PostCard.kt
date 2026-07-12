package com.example.mbtichatfriend.ui.community

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.mbtichatfriend.ui.components.SkeletonBox

private val REPORT_REASONS = listOf("불쾌한 내용", "스팸/광고", "개인정보 노출")

@Composable
fun PostCard(
    post: CommunityPostUi,
    onEmpathyClick: () -> Unit,
    onShareClick: () -> Unit = {},
    onCardClick: () -> Unit = {},
    onReport: (reason: String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    var showMenu by remember { mutableStateOf(false) }
    var showReportDialog by remember { mutableStateOf(false) }

    // 신고 사유 선택 다이얼로그
    if (showReportDialog) {
        AlertDialog(
            onDismissRequest = { showReportDialog = false },
            title = { Text("신고 사유 선택") },
            text = {
                Column {
                    REPORT_REASONS.forEach { reason ->
                        TextButton(
                            onClick = {
                                onReport(reason)
                                showReportDialog = false
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                text = reason,
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                }
            },
            confirmButton = {},
            dismissButton = {
                TextButton(onClick = { showReportDialog = false }) {
                    Text("취소")
                }
            },
        )
    }

    Card(modifier = modifier.fillMaxWidth().clickable { onCardClick() }) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SuggestionChip(
                    onClick = {},
                    label = { Text(post.mbti, style = MaterialTheme.typography.labelSmall) },
                )
                Text(
                    post.anonymousName,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(8.dp))
            Text(post.content, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // 공유 버튼
                IconButton(onClick = onShareClick, modifier = Modifier.size(32.dp)) {
                    Icon(
                        imageVector = Icons.Filled.Share,
                        contentDescription = "공유",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.width(8.dp))
                // 더보기 버튼 + 드롭다운 메뉴
                Box {
                    IconButton(onClick = { showMenu = true }, modifier = Modifier.size(32.dp)) {
                        Icon(
                            imageVector = Icons.Filled.MoreVert,
                            contentDescription = "더보기",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    DropdownMenu(
                        expanded = showMenu,
                        onDismissRequest = { showMenu = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("신고하기") },
                            onClick = {
                                showMenu = false
                                showReportDialog = true
                            },
                        )
                    }
                }
                Spacer(Modifier.width(8.dp))
                // 공감 버튼
                IconButton(onClick = onEmpathyClick, modifier = Modifier.size(32.dp)) {
                    Icon(
                        imageVector = if (post.isEmpathized) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder,
                        contentDescription = "공감",
                        tint = if (post.isEmpathized) MaterialTheme.colorScheme.primary
                               else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    "${post.empathyCount}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    "💬 ${post.commentCount}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * U4: [PostCard]의 대략적 레이아웃(칩+이름 줄 / 본문 2줄 / 하단 아이콘 3개)을 흉내낸 스켈레톤.
 * 정확한 치수를 맞출 필요는 없음 — 로딩 중 레이아웃 점프 최소화 목적.
 */
@Composable
fun PostCardSkeleton(modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SkeletonBox(modifier = Modifier.width(48.dp).height(20.dp))
                SkeletonBox(modifier = Modifier.width(64.dp).height(14.dp))
            }
            Spacer(Modifier.height(8.dp))
            SkeletonBox(modifier = Modifier.fillMaxWidth().height(14.dp))
            Spacer(Modifier.height(6.dp))
            SkeletonBox(modifier = Modifier.fillMaxWidth(0.6f).height(14.dp))
            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SkeletonBox(modifier = Modifier.size(32.dp), shape = CircleShape)
                Spacer(Modifier.width(8.dp))
                SkeletonBox(modifier = Modifier.size(32.dp), shape = CircleShape)
                Spacer(Modifier.width(8.dp))
                SkeletonBox(modifier = Modifier.size(32.dp), shape = CircleShape)
            }
        }
    }
}
