package com.truth.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// The web app's palette (web/app/globals.css), so the brands match.
object TruthColors {
    val Bg = Color(0xFFFAFAF8)
    val BgAlt = Color(0xFFF0F0EC)
    val Surface = Color(0xFFFFFFFF)
    val Ink = Color(0xFF1A1A18)
    val InkMuted = Color(0xFF5C5C57)
    val Accent = Color(0xFFA62B3F)
    val AccentSoft = Color(0xFFF3DCE0)
    val Border = Color(0xFFE2E1DC)
    val Success = Color(0xFF3F7A52)
    val Danger = Color(0xFF8B1E1E)
    val Neutral = Color(0xFF6B6B64)
}

private val colors = lightColorScheme(
    primary = TruthColors.Accent,
    onPrimary = Color.White,
    primaryContainer = TruthColors.AccentSoft,
    onPrimaryContainer = TruthColors.Accent,
    background = TruthColors.Bg,
    onBackground = TruthColors.Ink,
    surface = TruthColors.Surface,
    onSurface = TruthColors.Ink,
    surfaceVariant = TruthColors.BgAlt,
    onSurfaceVariant = TruthColors.InkMuted,
    outline = TruthColors.Border,
    outlineVariant = TruthColors.Border,
    error = TruthColors.Danger,
)

private val typography = Typography().run {
    copy(
        headlineMedium = headlineMedium.copy(fontFamily = FontFamily.Serif, fontWeight = FontWeight.SemiBold),
        headlineSmall = headlineSmall.copy(fontFamily = FontFamily.Serif, fontWeight = FontWeight.SemiBold),
        titleLarge = titleLarge.copy(fontFamily = FontFamily.Serif, fontWeight = FontWeight.SemiBold),
    )
}

val LabelCaps = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.8.sp)

@Composable
fun TruthTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, typography = typography, content = content)
}
