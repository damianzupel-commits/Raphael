package com.jarvisremote.app.ui.mando

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

private val GBG = Color(0xFF05070D)
private val GTXT = Color(0xFFDFE9F5)
private val GMUT = Color(0xFF7D93AC)
private val EDGE = Color(0x26355E7F)
private const val FOCAL = 1000f

private val PALETTE = listOf(
    Color(0xFF35E6FF), Color(0xFF49F0A6), Color(0xFFB78CFF),
    Color(0xFFFFC24D), Color(0xFF5CE1A8), Color(0xFF8CA2FF), Color(0xFFFF9E5C),
)

private fun colorFor(category: String): Color =
    if (category.isBlank()) Color(0xFF55708C) else PALETTE[abs(category.hashCode()) % PALETTE.size]

/** Proyecta un nodo 3D a pantalla con rotación (yaw/pitch) + zoom + perspectiva.
 *  Devuelve [screenX, screenY, profundidad(z), factorPerspectiva]. */
private fun project(n: LaidNode, yaw: Float, pitch: Float, zoom: Float, cx: Float, cy: Float): FloatArray {
    val cosY = cos(yaw); val sinY = sin(yaw)
    val cosX = cos(pitch); val sinX = sin(pitch)
    val x1 = n.x * cosY + n.z * sinY
    val z1 = -n.x * sinY + n.z * cosY
    val y2 = n.y * cosX - z1 * sinX
    val z2 = n.y * sinX + z1 * cosX
    val denom = FOCAL + z2
    val p = if (denom > 1f) FOCAL / denom else FOCAL
    return floatArrayOf(cx + x1 * p * zoom, cy + y2 * p * zoom, z2, p)
}

/** Grafo del vault de Obsidian en 3D, nativo (Compose Canvas). Arrastrás para ROTAR,
 *  pellizcás para zoom, tocás un nodo para ver su título. Posiciones de GraphViewModel. */
@Composable
fun GraphOverlay(onClose: () -> Unit) {
    val vm: GraphViewModel = viewModel()
    val ui by vm.ui.collectAsState()

    var yaw by remember { mutableStateOf(0.4f) }
    var pitch by remember { mutableStateOf(0.2f) }
    var zoom by remember { mutableStateOf(1f) }
    var selected by remember { mutableStateOf<LaidNode?>(null) }

    Box(
        Modifier
            .fillMaxSize()
            .background(GBG),
    ) {
        if (ui.nodes.isNotEmpty()) {
            Box(
                Modifier
                    .fillMaxSize()
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoomChange, _ ->
                            yaw += pan.x * 0.008f
                            pitch = (pitch + pan.y * 0.008f).coerceIn(-1.4f, 1.4f)
                            zoom = (zoom * zoomChange).coerceIn(0.2f, 6f)
                        }
                    }
                    .pointerInput(ui.nodes) {
                        detectTapGestures { tap ->
                            val cx = size.width / 2f; val cy = size.height / 2f
                            var best = -1; var bestD = Float.MAX_VALUE
                            ui.nodes.forEachIndexed { i, nd ->
                                val pr = project(nd, yaw, pitch, zoom, cx, cy)
                                val d = hypot(pr[0] - tap.x, pr[1] - tap.y)
                                if (d < bestD) { bestD = d; best = i }
                            }
                            selected = if (best >= 0 && bestD < 48f) ui.nodes[best] else null
                        }
                    },
            ) {
                Canvas(Modifier.fillMaxSize()) {
                    val cx = size.width / 2f; val cy = size.height / 2f
                    val proj = Array(ui.nodes.size) { project(ui.nodes[it], yaw, pitch, zoom, cx, cy) }
                    // aristas (debajo)
                    ui.edges.forEach { (a, b) ->
                        drawLine(
                            color = EDGE,
                            start = Offset(proj[a][0], proj[a][1]),
                            end = Offset(proj[b][0], proj[b][1]),
                            strokeWidth = 1.2f,
                        )
                    }
                    // nodos, de atrás hacia adelante (los de atrás primero)
                    val order = ui.nodes.indices.sortedByDescending { proj[it][2] }
                    order.forEach { i ->
                        val pr = proj[i]; val n = ui.nodes[i]
                        val persp = pr[3]
                        val r = (3f + n.degree.coerceAtMost(10) * 0.8f) * persp.coerceIn(0.5f, 1.8f)
                        val alpha = (((persp - 0.64f) / 1.6f).coerceIn(0f, 1f) * 0.7f + 0.3f)
                        val sp = Offset(pr[0], pr[1])
                        if (n.id == selected?.id) drawCircle(Color.White, radius = r + 4f, center = sp)
                        drawCircle(colorFor(n.category).copy(alpha = alpha), radius = r, center = sp)
                    }
                }
            }
        }

        // Header.
        Row(
            Modifier
                .fillMaxWidth()
                .background(Color(0xCC070C15))
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("GRAFO DE CONOCIMIENTO · 3D", color = GTXT, fontSize = 13.sp, letterSpacing = 2.sp)
                Text(
                    if (ui.loading) "calculando…" else "${ui.nodes.size} notas · arrastrá para rotar, pellizcá para zoom",
                    color = GMUT,
                    fontSize = 10.sp,
                )
            }
            IconButton(onClick = onClose) {
                Icon(Icons.Default.Close, contentDescription = "Cerrar", tint = GTXT)
            }
        }

        when {
            ui.loading -> CircularProgressIndicator(Modifier.align(Alignment.Center), color = Color(0xFF35E6FF))
            ui.error != null -> Text(
                ui.error ?: "",
                color = Color(0xFFFF6B6B),
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
            )
            ui.nodes.isEmpty() -> Text(
                "El vault no tiene notas enlazadas todavía.",
                color = GMUT,
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
            )
        }

        selected?.let { n ->
            Row(
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(Color(0xCC0B111C))
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier
                        .padding(end = 10.dp)
                        .size(10.dp)
                        .background(colorFor(n.category), CircleShape),
                )
                Column(Modifier.weight(1f)) {
                    Text(n.title, color = GTXT, fontSize = 14.sp)
                    Text(
                        n.category.ifBlank { "sin categoría" } + " · ${n.degree} conexiones",
                        color = GMUT,
                        fontSize = 10.sp,
                    )
                }
            }
        }
    }
}
