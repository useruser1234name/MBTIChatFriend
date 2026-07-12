package com.example.mbtichatfriend.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = PastelPurple,
    onPrimary = TextDark,
    primaryContainer = PastelPurpleLight,
    onPrimaryContainer = TextDark,
    secondary = PastelPink,
    onSecondary = TextDark,
    secondaryContainer = PastelPinkLight,
    onSecondaryContainer = TextDark,
    tertiary = SoftMint,
    onTertiary = TextDark,
    tertiaryContainer = SoftYellow,
    onTertiaryContainer = TextDark,
    background = CreamWhite,
    onBackground = TextDark,
    surface = PureWhite,
    onSurface = TextDark,
    surfaceVariant = Color(0xFFF5F0FF),
    onSurfaceVariant = TextMedium,
    outline = Color(0xFFE0D4FF),
    outlineVariant = Color(0xFFF0EBF9)
)

private val DarkColorScheme = darkColorScheme(
    primary = PastelPurple,
    onPrimary = Color.White,
    primaryContainer = DarkCard,
    onPrimaryContainer = PastelPurpleLight,
    secondary = PastelPink,
    onSecondary = Color.White,
    secondaryContainer = DarkCard,
    onSecondaryContainer = PastelPinkLight,
    tertiary = SoftMint,
    onTertiary = DarkNavy,
    background = DarkNavy,
    onBackground = Color.White,
    surface = DarkSurface,
    onSurface = Color.White,
    surfaceVariant = DarkCard,
    onSurfaceVariant = Color(0xFFB0B0C0),
    outline = Color(0xFF4A4B60),
    outlineVariant = Color(0xFF35364A)
)

@Composable
fun MBTIChatFriendTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        shapes = AppShapes,
        content = content
    )
}
