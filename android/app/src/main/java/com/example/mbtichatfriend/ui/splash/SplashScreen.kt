package com.example.mbtichatfriend.ui.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.mbtichatfriend.ui.theme.PastelPink
import com.example.mbtichatfriend.ui.theme.PastelPurple
import com.example.mbtichatfriend.ui.theme.SoftMint
import com.example.mbtichatfriend.ui.theme.SoftYellow
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(
    onFinished: () -> Unit
) {
    val fadeAnim = remember { Animatable(0f) }
    val scaleAnim = remember { Animatable(0.8f) }
    val subtitleFade = remember { Animatable(0f) }

    val infiniteTransition = rememberInfiniteTransition(label = "splash")
    val bounceY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -15f,
        animationSpec = infiniteRepeatable(
            tween(1000, easing = FastOutSlowInEasing),
            RepeatMode.Reverse
        ),
        label = "bounce"
    )

    // 장식 원들의 위치 애니메이션
    val decorFloat by infiniteTransition.animateFloat(
        initialValue = -8f,
        targetValue = 8f,
        animationSpec = infiniteRepeatable(
            tween(2000, easing = FastOutSlowInEasing),
            RepeatMode.Reverse
        ),
        label = "decor"
    )

    LaunchedEffect(Unit) {
        fadeAnim.animateTo(1f, animationSpec = tween(800))
        scaleAnim.animateTo(1f, animationSpec = tween(600))
        subtitleFade.animateTo(1f, animationSpec = tween(600))
        delay(1000)
        onFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(
                        PastelPurple.copy(alpha = 0.25f),
                        PastelPink.copy(alpha = 0.2f),
                        MaterialTheme.colorScheme.background
                    )
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        // 장식용 배경 원들
        Box(
            modifier = Modifier
                .offset(x = (-80).dp, y = (-180).dp + decorFloat.dp)
                .size(120.dp)
                .clip(CircleShape)
                .background(PastelPink.copy(alpha = 0.15f * fadeAnim.value))
        )
        Box(
            modifier = Modifier
                .offset(x = 100.dp, y = (-120).dp + (-decorFloat).dp)
                .size(80.dp)
                .clip(CircleShape)
                .background(SoftMint.copy(alpha = 0.2f * fadeAnim.value))
        )
        Box(
            modifier = Modifier
                .offset(x = (-60).dp, y = 200.dp + decorFloat.dp)
                .size(100.dp)
                .clip(CircleShape)
                .background(SoftYellow.copy(alpha = 0.15f * fadeAnim.value))
        )
        Box(
            modifier = Modifier
                .offset(x = 120.dp, y = 160.dp + (-decorFloat).dp)
                .size(60.dp)
                .clip(CircleShape)
                .background(PastelPurple.copy(alpha = 0.12f * fadeAnim.value))
        )

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier
                .alpha(fadeAnim.value)
                .scale(scaleAnim.value)
        ) {
            // 로고 아이콘 영역
            Surface(
                modifier = Modifier
                    .size(100.dp)
                    .offset(y = bounceY.dp),
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                tonalElevation = 4.dp
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Surface(
                        modifier = Modifier.size(72.dp),
                        shape = RoundedCornerShape(20.dp),
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.25f)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                text = "MBTI",
                                fontSize = 22.sp,
                                fontWeight = FontWeight.ExtraBold,
                                color = MaterialTheme.colorScheme.primary,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

            Text(
                text = "Chat Friend",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(Modifier.height(12.dp))

            // 부제목 with fade-in
            Text(
                text = "나만의 AI 친구와 대화해요",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.alpha(subtitleFade.value)
            )

            Spacer(Modifier.height(24.dp))

            // 미니 캐릭터 표정 행
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.alpha(subtitleFade.value)
            ) {
                listOf("^^", "<3", ":P", "?!", "//").forEachIndexed { idx, emoji ->
                    val itemBounce by infiniteTransition.animateFloat(
                        initialValue = 0f,
                        targetValue = -6f,
                        animationSpec = infiniteRepeatable(
                            tween(600, delayMillis = idx * 120),
                            RepeatMode.Reverse
                        ),
                        label = "emoji$idx"
                    )
                    Surface(
                        modifier = Modifier
                            .size(36.dp)
                            .offset(y = itemBounce.dp),
                        shape = CircleShape,
                        color = listOf(
                            PastelPink, PastelPurple, SoftMint, SoftYellow, PastelPink
                        )[idx].copy(alpha = 0.3f)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(emoji, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}
