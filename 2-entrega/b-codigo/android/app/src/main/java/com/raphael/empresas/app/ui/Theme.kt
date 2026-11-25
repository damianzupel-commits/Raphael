package com.raphael.empresas.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// La paleta del panel de Raphael en la PC (widgets.py): fondo azul noche, tarjetas azuladas y acentos cian.
val Night = Color(0xFF0F1521)        // BG
val NightPanel = Color(0xFF111A28)   // PANEL
val NightCard = Color(0xFF162234)    // CARD
val CardBorder = Color(0xFF283B59)
val PanelBorder = Color(0xFF24344E)
val ActiveBg = Color(0xFF13384C)
val ActiveBorder = Color(0xFF1D4A60)
val InputBg = Color(0xFF0A101A)
val Cyan = Color(0xFF35E0FF)
val CyanSoft = Color(0xFF7FE9FF)
val TextMain = Color(0xFFE8F0FF)
val Muted = Color(0xFF7F8DB0)
val Dim = Color(0xFF59606D)
val Warn = Color(0xFFFF7922)         // ORANGE
val Bad = Color(0xFFFF6B7A)
val Good = Color(0xFF3DDC97)
val OnCyan = Color(0xFF04121A)

private val Dark = darkColorScheme(
    primary = Cyan, onPrimary = OnCyan, secondary = CyanSoft, onSecondary = OnCyan,
    background = Night, onBackground = TextMain, surface = NightCard, onSurface = TextMain,
    surfaceVariant = Color(0xFF1B2A42), onSurfaceVariant = Muted, error = Bad, tertiary = Warn,
    outline = CardBorder, outlineVariant = PanelBorder,
)
@Composable
fun RaphaelTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Dark, content = content)   // siempre oscuro: es la marca de Raphael
}
