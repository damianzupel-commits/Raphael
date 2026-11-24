package com.jarvisremote.app.ui.mando

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jarvisremote.app.data.BrigadeMeta
import com.jarvisremote.app.data.BrigadeRuntime
import kotlinx.coroutines.delay

private val BG = Color(0xFF05070D)
private val PANEL = Color(0xFF0E1726)
private val LINE = Color(0xFF1B2A3F)
private val TXT = Color(0xFFDFE9F5)
private val MUT = Color(0xFF7D93AC)
private val OKC = Color(0xFF39D98A)
private val BAD = Color(0xFFFF6B6B)

/** Acento e ícono por brigada (solo presentación; el estado llega del backend). */
private fun accentFor(id: String): Color = when (id) {
    "seg" -> Color(0xFF35E6FF)
    "mal" -> Color(0xFFFF5C7A)
    "inv" -> Color(0xFFB78CFF)
    "mem" -> Color(0xFF49F0A6)
    "ing" -> Color(0xFFFFC24D)
    "trd" -> Color(0xFF5CE1A8)
    "ops" -> Color(0xFF8CA2FF)
    "rep" -> Color(0xFFFF9E5C)
    "con" -> Color(0xFFB0B8C4)
    "geo" -> Color(0xFF4FD6C9)
    else -> Color(0xFF35E6FF)
}

private fun iconFor(id: String): String = when (id) {
    "seg" -> "🛡️"
    "mal" -> "🦠"
    "inv" -> "🔎"
    "mem" -> "🧠"
    "ing" -> "📥"
    "trd" -> "📈"
    "ops" -> "🖥️"
    "rep" -> "🔧"
    "con" -> "🎬"
    "geo" -> "🌐"
    else -> "⬡"
}

private fun ago(ts: Double, nowSec: Long): String {
    if (ts <= 0.0) return "—"
    val d = nowSec - ts.toLong()
    return when {
        d < 2 -> "ahora"
        d < 60 -> "hace ${d}s"
        d < 3600 -> "hace ${d / 60} min"
        else -> "hace ${d / 3600} h"
    }
}

/** Una estación = un "soldado" de la brigada, con su tier. */
private data class Station(val role: String, val tier: Int)

private val TIER_MODEL = mapOf(
    0 to "determinista · sin modelo",
    1 to "jarvis-text-v2 local",
    2 to "free rotativo",
    3 to "Sonnet 5.5",
    4 to "Opus 5.5",
)

/** Escuadrón por brigada (espeja SQUADS del panel de la PC). Seguridad y Trading son las
 *  REALES del código; el resto son propuestas (brigadas aún no orquestadas). */
private val SQUADS: Map<String, List<Station>> = mapOf(
    "seg" to listOf(Station("Reconocimiento", 0), Station("Contexto", 0), Station("Triage", 3), Station("Config", 0), Station("Redacción", 3), Station("Catador", 3), Station("Ensamble", 0)),
    "trd" to listOf(Station("Datos", 0), Station("Estructura", 0), Station("Liquidez", 0), Station("Zonas", 0), Station("POI", 0), Station("Riesgo", 0), Station("Señal", 0), Station("Lectura", 3)),
    "mal" to listOf(Station("Vigilancia (YARA/FIM)", 0), Station("Heurística conductual", 0), Station("Cuarentena", 0)),
    "inv" to listOf(Station("Captura de evidencia", 0), Station("Análisis", 3), Station("Firma Ed25519", 0)),
    "mem" to listOf(Station("Activación/difusión", 0), Station("Consolidación (sueño)", 1), Station("Curiosidad", 1)),
    "ing" to listOf(Station("Fetch/transcript", 0), Station("Embeddings (nomic)", 0), Station("Relevancia", 2)),
    "ops" to listOf(Station("Monitor de tools (en vivo)", 0), Station("Supervisor · valida y destraba", 3)),
    "rep" to listOf(Station("Propuesta de fix", 4), Station("Guardrail líneas rojas", 0)),
    "con" to listOf(Station("Generación (ComfyUI)", 0)),
    "geo" to listOf(Station("Geolocalización IP", 0), Station("Rastreo cripto", 0), Station("Mapa en vivo", 0)),
)

private val REAL_BRIGADES = setOf("seg", "trd", "geo")

private fun tierColor(tier: Int): Color = when (tier) {
    0 -> Color(0xFF7D93AC) // determinista
    1 -> Color(0xFF49F0A6) // local
    2 -> Color(0xFFFFC24D) // free
    3 -> Color(0xFF35E6FF) // Sonnet
    4 -> Color(0xFFB78CFF) // Opus
    else -> MUT
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionControlScreen(onBack: () -> Unit, viewModel: MissionControlViewModel = viewModel()) {
    val ui by viewModel.ui.collectAsState()
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    var showGraph by rememberSaveable { mutableStateOf(false) }
    var showGlobo by rememberSaveable { mutableStateOf(false) }

    // Reloj que tiquea cada segundo para que la "actividad reciente" se apague sola.
    val nowSec by produceState(initialValue = System.currentTimeMillis() / 1000L) {
        while (true) {
            value = System.currentTimeMillis() / 1000L
            delay(1000)
        }
    }

    Box(Modifier.fillMaxSize().background(BG)) {
        Scaffold(
            containerColor = Color.Transparent,
            topBar = {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color(0xFF070C15),
                        titleContentColor = TXT,
                        navigationIconContentColor = TXT,
                        actionIconContentColor = TXT,
                    ),
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                        }
                    },
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            PulseDot(color = if (ui.connected) OKC else BAD)
                            Spacer(Modifier.width(10.dp))
                            Text(
                                "CENTRO DE MANDO",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.SemiBold,
                                letterSpacing = 3.sp,
                            )
                        }
                    },
                    actions = {
                        Text(
                            if (ui.connected) "EN VIVO" else "SIN CONEXIÓN",
                            color = if (ui.connected) OKC else BAD,
                            fontSize = 10.sp,
                            letterSpacing = 1.5.sp,
                            modifier = Modifier.padding(end = 14.dp),
                        )
                    },
                )
            },
        ) { padding ->
            Column(
                Modifier
                    .padding(padding)
                    .fillMaxSize(),
            ) {
                MaestroStrip(ui.masterModel)
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    contentPadding = PaddingValues(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(items = ui.brigades, key = { it.id }) { b ->
                        BrigadeCard(
                            meta = b,
                            rt = ui.runtime[b.id] ?: BrigadeRuntime(),
                            nowSec = nowSec,
                            // Geolocalización abre el mapa directo (ya con capas + chat embebidos).
                            onClick = { if (b.id == "geo") showGlobo = true else selected = b.id },
                        )
                    }
                }
            }
        }

        // Detalle de brigada (overlay).
        AnimatedVisibility(visible = selected != null, enter = fadeIn(), exit = fadeOut()) {
            val meta = ui.brigades.firstOrNull { it.id == selected }
            if (meta != null) {
                BrigadeDetail(
                    meta = meta,
                    rt = ui.runtime[meta.id] ?: BrigadeRuntime(),
                    nowSec = nowSec,
                    connected = ui.connected,
                    onClose = { selected = null },
                    onOpenGraph = { showGraph = true },
                    onOpenGlobo = { showGlobo = true },
                )
            }
        }

        // Grafo de conocimiento (brigada Memoria), nativo, por encima del detalle.
        AnimatedVisibility(visible = showGraph, enter = fadeIn(), exit = fadeOut()) {
            GraphOverlay(onClose = { showGraph = false })
        }

        // Mapa de inteligencia / globo (brigada Geolocalización pública), por encima del detalle.
        AnimatedVisibility(visible = showGlobo, enter = fadeIn(), exit = fadeOut()) {
            GloboOverlay(onClose = { showGlobo = false })
        }
    }
}

@Composable
private fun PulseDot(color: Color, size: Int = 11) {
    val t = rememberInfiniteTransition(label = "dot")
    val a by t.animateFloat(
        initialValue = 0.4f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1200, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "dotA",
    )
    Box(
        Modifier
            .size(size.dp)
            .alpha(a)
            .background(color, CircleShape),
    )
}

@Composable
private fun MaestroStrip(model: String) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(
                Brush.horizontalGradient(listOf(Color(0xFF0C1526), Color(0xFF0A1120))),
            )
            .border(1.dp, LINE)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("👑", fontSize = 18.sp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text("ORQUESTADOR MAESTRO", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
            Text(model, color = TXT, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        }
        Text("coordina las brigadas", color = MUT, fontSize = 11.sp)
    }
}

@Composable
private fun BrigadeCard(
    meta: BrigadeMeta,
    rt: BrigadeRuntime,
    nowSec: Long,
    onClick: () -> Unit,
) {
    val accent = accentFor(meta.id)
    val active = rt.ts > 0.0 && (nowSec - rt.ts.toLong()) < 8
    val future = meta.future

    val t = rememberInfiniteTransition(label = "card-${meta.id}")
    val glow by t.animateFloat(
        initialValue = if (active) 0.35f else 0f,
        targetValue = if (active) 0.95f else 0f,
        animationSpec = infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "glow",
    )
    val borderAlpha = if (active) 0.4f + glow * 0.6f else 0.25f

    Column(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 150.dp)
            .alpha(if (future) 0.55f else 1f)
            .background(PANEL, RoundedCornerShape(16.dp))
            .border(1.dp, accent.copy(alpha = borderAlpha), RoundedCornerShape(16.dp))
            .clickable(enabled = !future, onClick = onClick)
            .padding(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(iconFor(meta.id), fontSize = 22.sp)
            Spacer(Modifier.weight(1f))
            if (active) {
                Box(
                    Modifier
                        .size(8.dp)
                        .alpha(0.5f + glow * 0.5f)
                        .background(accent, CircleShape),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(meta.nm, color = TXT, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(meta.sub, color = MUT, fontSize = 9.5.sp, letterSpacing = 1.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)

        rt.mode?.takeIf { it.isNotBlank() }?.let { mode ->
            Spacer(Modifier.height(6.dp))
            ModePill(mode, accent)
        }

        Spacer(Modifier.weight(1f))
        Spacer(Modifier.height(8.dp))
        if (future) {
            Text("PRÓXIMAMENTE", color = accent, fontSize = 9.sp, letterSpacing = 1.5.sp)
        } else {
            Row(verticalAlignment = Alignment.Bottom) {
                Text("${rt.count}", color = accent, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(4.dp))
                Text("acciones", color = MUT, fontSize = 10.sp, modifier = Modifier.padding(bottom = 3.dp))
            }
            Text(rt.last, color = MUT, fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun ModePill(mode: String, accent: Color) {
    Text(
        mode,
        color = accent,
        fontSize = 10.sp,
        fontWeight = FontWeight.Medium,
        modifier = Modifier
            .background(accent.copy(alpha = 0.14f), RoundedCornerShape(20.dp))
            .border(1.dp, accent.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
            .padding(horizontal = 9.dp, vertical = 3.dp),
    )
}

@Composable
private fun BrigadeDetail(
    meta: BrigadeMeta,
    rt: BrigadeRuntime,
    nowSec: Long,
    connected: Boolean,
    onClose: () -> Unit,
    onOpenGraph: () -> Unit = {},
    onOpenGlobo: () -> Unit = {},
) {
    val accent = accentFor(meta.id)
    // Scrim que cierra al tocar afuera.
    Box(
        Modifier
            .fillMaxSize()
            .background(Color(0xCC03060C))
            .clickable(onClick = onClose),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.9f)
                .padding(20.dp)
                .background(Color(0xFF0B111C), RoundedCornerShape(20.dp))
                .border(1.dp, accent.copy(alpha = 0.5f), RoundedCornerShape(20.dp))
                // Consume los taps dentro de la tarjeta para que no lleguen al scrim y la cierren.
                .pointerInput(Unit) { detectTapGestures {} }
                .verticalScroll(rememberScrollState())
                .padding(22.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(iconFor(meta.id), fontSize = 30.sp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(meta.nm, color = TXT, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text(meta.sub, color = MUT, fontSize = 10.sp, letterSpacing = 1.5.sp)
                }
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.Close, contentDescription = "Cerrar", tint = MUT)
                }
            }

            rt.mode?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(12.dp))
                ModePill(it, accent)
            }

            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth()) {
                Stat("Acciones", "${rt.count}", accent, Modifier.weight(1f))
                Stat("Última", ago(rt.ts, nowSec), TXT, Modifier.weight(1f))
                Stat("Estado", if (connected) "en vivo" else "offline", if (connected) OKC else BAD, Modifier.weight(1f))
            }

            // Brigada Ingesta: fuentes auto-ingeridas + últimos ítems ingeridos (interactivo).
            if (meta.id == "ing") {
                Spacer(Modifier.height(22.dp))
                IngestSection(accent)
            }

            // Brigada Investigación: casos de research retenidos (abrir/cerrar).
            if (meta.id == "inv") {
                Spacer(Modifier.height(22.dp))
                InvestigationSection(accent)
            }

            // Brigada Memoria: abre el grafo de conocimiento (nativo).
            if (meta.id == "mem") {
                Spacer(Modifier.height(22.dp))
                Button(onClick = onOpenGraph, modifier = Modifier.fillMaxWidth()) {
                    Text("🧠  Ver grafo de conocimiento")
                }
            }

            // Brigada Trading: watchlist de símbolos con su estado (solo análisis).
            if (meta.id == "trd") {
                Spacer(Modifier.height(22.dp))
                TradingSection(accent)
            }

            // Brigada Geolocalización pública: abre el mapa de inteligencia (globo).
            if (meta.id == "geo") {
                Spacer(Modifier.height(22.dp))
                Button(onClick = onOpenGlobo, modifier = Modifier.fillMaxWidth()) {
                    Text("🌐  Abrir el mapa de inteligencia")
                }
            }

            Spacer(Modifier.height(20.dp))
            Text("ÚLTIMA ACCIÓN", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
            Spacer(Modifier.height(6.dp))
            Text(
                rt.last,
                color = TXT,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF060B14), RoundedCornerShape(10.dp))
                    .border(1.dp, LINE, RoundedCornerShape(10.dp))
                    .padding(12.dp),
            )

            if (rt.recent.size > 1) {
                Spacer(Modifier.height(18.dp))
                Text("ACTIVIDAD EN VIVO", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
                Spacer(Modifier.height(8.dp))
                rt.recent.forEach { a ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            Modifier
                                .size(5.dp)
                                .background(accent.copy(alpha = 0.7f), CircleShape),
                        )
                        Spacer(Modifier.width(9.dp))
                        Text(
                            a.m,
                            color = TXT,
                            fontSize = 12.5.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f),
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(ago(a.ts, nowSec), color = MUT, fontSize = 10.sp)
                    }
                }
            }

            if (meta.modes.isNotEmpty()) {
                Spacer(Modifier.height(18.dp))
                Text("MODOS", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    meta.modes.forEach { ModePill(it, accent) }
                }
            }

            val squad = SQUADS[meta.id].orEmpty()
            if (squad.isNotEmpty()) {
                Spacer(Modifier.height(20.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("ESCUADRÓN · ${squad.size} ESTACIONES", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
                    Spacer(Modifier.width(8.dp))
                    if (meta.id !in REAL_BRIGADES) {
                        Text(
                            "propuesta",
                            color = MUT,
                            fontSize = 9.sp,
                            modifier = Modifier
                                .background(Color(0xFF162234), RoundedCornerShape(20.dp))
                                .padding(horizontal = 7.dp, vertical = 2.dp),
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                squad.forEach { StationRow(it) }
            }
        }
    }
}

@Composable
private fun StationRow(st: Station) {
    val c = tierColor(st.tier)
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(7.dp)
                .background(c, CircleShape),
        )
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(st.role, color = TXT, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Text(TIER_MODEL[st.tier] ?: "", color = MUT, fontSize = 10.sp)
        }
        Text(
            "TIER ${st.tier}",
            color = c,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier
                .background(c.copy(alpha = 0.14f), RoundedCornerShape(20.dp))
                .border(1.dp, c.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
                .padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}

@Composable
private fun Stat(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, color = color, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(label, color = MUT, fontSize = 10.sp)
    }
}

@Composable
private fun TradingSection(accent: Color) {
    val vm: TradingViewModel = androidx.lifecycle.viewmodel.compose.viewModel()
    val ui by vm.ui.collectAsState()
    var newSym by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = TXT, unfocusedTextColor = TXT,
        focusedBorderColor = accent, unfocusedBorderColor = LINE,
        cursorColor = accent,
        focusedContainerColor = Color(0xFF060B14), unfocusedContainerColor = Color(0xFF060B14),
        focusedPlaceholderColor = MUT, unfocusedPlaceholderColor = MUT,
    )

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("WATCHLIST", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp, modifier = Modifier.weight(1f))
        TextButton(onClick = { vm.refresh() }, enabled = !ui.refreshing) {
            Text(if (ui.refreshing) "actualizando…" else "Actualizar", color = accent, fontSize = 11.sp)
        }
    }
    Spacer(Modifier.height(6.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = newSym,
            onValueChange = { newSym = it },
            placeholder = { Text("Símbolo (ej. BTC/USDT)", color = MUT, fontSize = 12.sp) },
            singleLine = true,
            colors = fieldColors,
            modifier = Modifier.weight(1f),
        )
        Spacer(Modifier.width(8.dp))
        Button(onClick = { vm.add(newSym); newSym = "" }, enabled = newSym.isNotBlank()) {
            Text("Agregar")
        }
    }

    Spacer(Modifier.height(12.dp))
    when {
        ui.loading -> Text("Cargando…", color = MUT, fontSize = 12.sp)
        ui.error != null -> Text(ui.error ?: "", color = BAD, fontSize = 12.sp)
        ui.symbols.isEmpty() -> Text(
            "Sin símbolos. Agregá uno y tocá Actualizar para ver su setup.",
            color = MUT,
            fontSize = 12.sp,
        )
        else -> ui.symbols.forEach { s ->
            val estadoColor = when (s.estado) {
                "señal activa" -> OKC
                "setup formándose" -> Color(0xFFFFC24D)
                else -> MUT
            }
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(s.instrument, color = TXT, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                        s.direction?.let {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                if (it == "long") "▲ LONG" else "▼ SHORT",
                                color = if (it == "long") OKC else BAD,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                        if (s.demo) {
                            Spacer(Modifier.width(8.dp))
                            Text("DEMO", color = MUT, fontSize = 8.5.sp)
                        }
                    }
                    val meta = buildString {
                        append(s.estado ?: "sin evaluar")
                        s.rr?.let { append(" · R:R ${(it * 10).toInt() / 10.0}") }
                        s.confidence?.let { append(" · conf ${(it * 100).toInt()}%") }
                        s.winRate?.let { append(" · aciertos ${(it * 100).toInt()}%") }
                    }
                    Text(meta, color = estadoColor, fontSize = 10.sp)
                    if (s.entry != null) {
                        val risk = buildString {
                            append("E ${s.entry}  SL ${s.sl}  TP ${s.tp}")
                            s.units?.let { append("  ·  ${it}u") }
                            s.riskCash?.let { append(" (\$$it)") }
                        }
                        Text(risk, color = MUT, fontSize = 9.5.sp, fontFamily = FontFamily.Monospace, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
                TextButton(onClick = { vm.backtest(s.instrument) }) {
                    Text("Backtest", color = accent, fontSize = 10.sp)
                }
                IconButton(onClick = { vm.remove(s.instrument) }) {
                    Icon(Icons.Default.Close, contentDescription = "Quitar", tint = MUT)
                }
            }
        }
    }
    Spacer(Modifier.height(8.dp))
    Text("Solo análisis — Raphael nunca opera solo.", color = MUT, fontSize = 9.5.sp)
}

@Composable
private fun InvestigationSection(accent: Color) {
    val vm: InvestigationViewModel = androidx.lifecycle.viewmodel.compose.viewModel()
    val ui by vm.ui.collectAsState()

    Text("INVESTIGACIONES", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
    Spacer(Modifier.height(8.dp))
    when {
        ui.loading -> Text("Cargando…", color = MUT, fontSize = 12.sp)
        ui.error != null -> Text(ui.error ?: "", color = BAD, fontSize = 12.sp)
        ui.cases.isEmpty() -> Text(
            "Sin investigaciones todavía. Pedile a Raphael \"investiga …\" y aparece acá.",
            color = MUT,
            fontSize = 12.sp,
        )
        else -> ui.cases.forEach { c ->
            val open = c.status == "abierta"
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier
                        .size(7.dp)
                        .background(if (open) accent else MUT, CircleShape),
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(c.title, color = TXT, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(
                        (if (open) "abierta" else "cerrada") + " · ${c.findings} hallazgos",
                        color = MUT,
                        fontSize = 10.sp,
                    )
                }
                TextButton(onClick = { vm.setStatus(c.id, if (open) "cerrada" else "abierta") }) {
                    Text(if (open) "Cerrar" else "Reabrir", color = accent, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun IngestSection(accent: Color) {
    val vm: IngestViewModel = androidx.lifecycle.viewmodel.compose.viewModel()
    val ui by vm.ui.collectAsState()
    val uriHandler = LocalUriHandler.current
    var newUrl by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = TXT, unfocusedTextColor = TXT,
        focusedBorderColor = accent, unfocusedBorderColor = LINE,
        cursorColor = accent,
        focusedContainerColor = Color(0xFF060B14), unfocusedContainerColor = Color(0xFF060B14),
        focusedPlaceholderColor = MUT, unfocusedPlaceholderColor = MUT,
    )

    Text("AGREGAR FUENTE (ingiere sola)", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
    Spacer(Modifier.height(8.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = newUrl,
            onValueChange = { newUrl = it },
            placeholder = { Text("Playlist o URL de YouTube", color = MUT, fontSize = 12.sp) },
            singleLine = true,
            colors = fieldColors,
            modifier = Modifier.weight(1f),
        )
        Spacer(Modifier.width(8.dp))
        Button(onClick = { vm.addSource(newUrl); newUrl = "" }, enabled = newUrl.isNotBlank()) {
            Text("Agregar")
        }
    }

    if (ui.sources.isNotEmpty()) {
        Spacer(Modifier.height(12.dp))
        ui.sources.forEach { src ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    src,
                    color = TXT,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier
                        .weight(1f)
                        .clickable { runCatching { uriHandler.openUri(src) } },
                )
                IconButton(onClick = { vm.removeSource(src) }) {
                    Icon(Icons.Default.Close, contentDescription = "Quitar fuente", tint = MUT)
                }
            }
        }
    }

    Spacer(Modifier.height(18.dp))
    Text("INGERIDO RECIENTEMENTE", color = MUT, fontSize = 10.sp, letterSpacing = 2.sp)
    Spacer(Modifier.height(8.dp))
    when {
        ui.loading -> Text("Cargando…", color = MUT, fontSize = 12.sp)
        ui.error != null -> Text(ui.error ?: "", color = BAD, fontSize = 12.sp)
        ui.recent.isEmpty() -> Text("Todavía no ingirió nada.", color = MUT, fontSize = 12.sp)
        else -> ui.recent.forEach { item ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = 5.dp)
                    .clickable { runCatching { uriHandler.openUri(item.url) } },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier
                        .size(6.dp)
                        .background(accent.copy(alpha = 0.7f), CircleShape),
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(item.title, color = TXT, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(item.url, color = MUT, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}
