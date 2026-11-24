package com.raphael.empresas.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// La estética del panel de Raphael: azul noche y cian.
val Night = Color(0xFF0B1220)
val NightCard = Color(0xFF131C2E)
val Cyan = Color(0xFF22D3EE)
val CyanSoft = Color(0xFF67E8F9)
val Warn = Color(0xFFF59E0B)
val Bad = Color(0xFFF87171)

private val Dark = darkColorScheme(
    primary = Cyan, onPrimary = Night, secondary = CyanSoft, onSecondary = Night,
    background = Night, onBackground = Color(0xFFE5E7EB), surface = NightCard, onSurface = Color(0xFFE5E7EB),
    surfaceVariant = Color(0xFF1C2740), onSurfaceVariant = Color(0xFF9CA3AF), error = Bad, tertiary = Warn,
)
@Composable
fun RaphaelTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Dark, content = content)   // siempre oscuro: es la marca de Raphael
}
