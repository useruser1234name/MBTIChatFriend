package com.example.mbtichatfriend.ui.theme

import androidx.compose.ui.graphics.Color

// Primary - 파스텔 핑크/퍼플
val PastelPink = Color(0xFFFFB5C2)
val PastelPinkLight = Color(0xFFFFD6DE)
val PastelPurple = Color(0xFFC9B1FF)
val PastelPurpleLight = Color(0xFFE0D4FF)

// Secondary - 소프트 민트/옐로우
val SoftMint = Color(0xFFB5E8D5)
val SoftYellow = Color(0xFFFFF3B0)

// Background
val CreamWhite = Color(0xFFFFF8F0)
val PureWhite = Color(0xFFFFFFFF)

// Dark mode
val DarkNavy = Color(0xFF1A1B2E)
val DarkSurface = Color(0xFF252640)
val DarkCard = Color(0xFF2E2F4A)

// Text
val TextDark = Color(0xFF2D2D3A)
val TextMedium = Color(0xFF6B6B7B)
// U8: 접근성 — 4.5:1 이상 대비 확보를 위해 어둡게 조정(배경 CreamWhite 대비 약 4.75:1). 현재 사용처 0건(미사용 토큰).
val TextLight = Color(0xFF6E6E80)

// Bubble colors - Light
val UserBubble = Color(0xFFC9B1FF)
val UserBubbleText = Color(0xFF2D2D3A)
val AiBubble = Color(0xFFFFFFFF)
val AiBubbleText = Color(0xFF2D2D3A)

// Bubble colors - Dark
val UserBubbleDark = Color(0xFF5A4B8A)
val UserBubbleTextDark = Color(0xFFFFFFFF)
val AiBubbleDark = Color(0xFF2E2F4A)
val AiBubbleTextDark = Color(0xFFE8E8F0)

// Accent
val AccentRed = Color(0xFFFF8A8A)
val AccentGreen = Color(0xFF8AE0B0)

// Emotion Bubble Tints (Light)
val EmotionLoveBubble = Color(0xFFFFF0F5)
val EmotionHappyBubble = Color(0xFFFFFDE7)
val EmotionAngryBubble = Color(0xFFFFEBEE)
val EmotionSadBubble = Color(0xFFE8F0FE)
val EmotionShyBubble = Color(0xFFFCE4EC)
val EmotionSurprisedBubble = Color(0xFFFFF8E1)
val EmotionPlayfulBubble = Color(0xFFF3E5F5)
val EmotionWorriedBubble = Color(0xFFE8EAF6)
val EmotionTouchedBubble = Color(0xFFFFF3E0)

// Emotion Bubble Tints (Dark)
val EmotionLoveBubbleDark = Color(0xFF3D2033)
val EmotionHappyBubbleDark = Color(0xFF3D3820)
val EmotionAngryBubbleDark = Color(0xFF3D2020)
val EmotionSadBubbleDark = Color(0xFF20283D)
val EmotionShyBubbleDark = Color(0xFF3D2028)
val EmotionSurprisedBubbleDark = Color(0xFF3D3520)
val EmotionPlayfulBubbleDark = Color(0xFF30203D)
val EmotionWorriedBubbleDark = Color(0xFF20223D)
val EmotionTouchedBubbleDark = Color(0xFF3D3020)

// Emotion Border Colors
val EmotionLoveBorder = Color(0xFFFFB5C2)
val EmotionHappyBorder = Color(0xFFFFD54F)
val EmotionAngryBorder = Color(0xFFFF8A8A)
val EmotionSadBorder = Color(0xFF90CAF9)
val EmotionShyBorder = Color(0xFFF8BBD0)
val EmotionPlayfulBorder = Color(0xFFCE93D8)
val EmotionWorriedBorder = Color(0xFF9FA8DA)
val EmotionTouchedBorder = Color(0xFFFFCC80)

// ── U2: 채팅 무대(호감도 그라데이션) 배경 - Light ─────────────────────────────
// (ChatScreen의 CharacterAnimationArea, 호감도 레벨 3~5 단계 무대 배경)
val AffinityBgLv5 = Color(0xFFFFF0F5)
val AffinityBgLv4 = Color(0xFFFCE4EC)
val AffinityBgLv3 = Color(0xFFFFF8E1)

// ── U2: 채팅 무대 배경 - Dark ──────────────────────────────────────────────
// 감정 버블 패턴과 동일한 소스 hue(라이트 값이 EmotionLoveBubble/EmotionShyBubble/
// EmotionSurprisedBubble과 각각 동일)라, 이미 검증된 대응 Dark 값을 그대로 재사용.
val AffinityBgLv5Dark = Color(0xFF3D2033)
val AffinityBgLv4Dark = Color(0xFF3D2028)
val AffinityBgLv3Dark = Color(0xFF3D3520)

// ── U2: 가정의 달 감사 카드 그라데이션 - Light ─────────────────────────────
val GratitudeOrange = Color(0xFFE8621A)
val GratitudeGold = Color(0xFFD4AF37)

// ── U2: 감사 카드 그라데이션 - Dark ────────────────────────────────────────
// hue 유지(각각 원본 대비 명도 ~50%)한 채도 낮춘 어두운 대응색 — DarkCard(0xFF2E2F4A) 계열과 어울리게 선정.
val GratitudeOrangeDark = Color(0xFF74310D)
val GratitudeGoldDark = Color(0xFF6A571B)
