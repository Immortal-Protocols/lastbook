package local.lastbook.android.ui.theme

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

private val Light = lightColorScheme(
    primary = Color(0xFF10805C),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE2F1EA),
    onPrimaryContainer = Color(0xFF0B2E22),
    secondary = Color(0xFF14453A),
    secondaryContainer = Color(0xFFE2F1EA),
    onSecondaryContainer = Color(0xFF0B2E22),
    background = Color(0xFFFFFFFF),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFF3F3F4),
    surfaceTint = Color.Transparent,
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFAFAFA),
    surfaceContainer = Color(0xFFF5F5F6),
    surfaceContainerHigh = Color(0xFFEFEFF1),
    surfaceContainerHighest = Color(0xFFE9E9EB),
    onSurface = Color(0xFF1D1D1F),
    onSurfaceVariant = Color(0xFF55555A),
    outline = Color(0xFFDCDCE0),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF3CC690),
    onPrimary = Color(0xFF06170F),
    primaryContainer = Color(0xFF173A2D),
    onPrimaryContainer = Color(0xFFDDF5E9),
    secondary = Color(0xFF8FDCC0),
    secondaryContainer = Color(0xFF173A2D),
    onSecondaryContainer = Color(0xFFDDF5E9),
    background = Color(0xFF1E1E1F),
    surface = Color(0xFF1E1E1F),
    surfaceVariant = Color(0xFF28282A),
    surfaceTint = Color.Transparent,
    surfaceContainerLowest = Color(0xFF1A1A1B),
    surfaceContainerLow = Color(0xFF222224),
    surfaceContainer = Color(0xFF262628),
    surfaceContainerHigh = Color(0xFF2C2C2E),
    surfaceContainerHighest = Color(0xFF333336),
    onSurface = Color(0xFFF2F2F3),
    onSurfaceVariant = Color(0xFFC2C2C7),
    outline = Color(0xFF3A3A3D),
)

@Composable
fun LastbookTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val scheme = if (dark) Dark else Light
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !dark
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = !dark
        }
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
