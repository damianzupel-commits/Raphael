package com.jarvisremote.app.ui.mando

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.GraphRepository
import com.jarvisremote.app.data.GraphResponse
import com.jarvisremote.app.data.SettingsRepository
import kotlin.math.sqrt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Un nodo ya posicionado por el layout 3D (coordenadas "mundo", centradas en 0). */
data class LaidNode(
    val id: String,
    val title: String,
    val category: String,
    val x: Float,
    val y: Float,
    val z: Float,
    val degree: Int,
)

data class GraphUi(
    val nodes: List<LaidNode> = emptyList(),
    val edges: List<Pair<Int, Int>> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
)

// Tope alto: cubre las ~410 notas del vault con holgura. Más que esto degrada a las más
// conectadas, porque el layout es O(n²) y se volvería lento.
private const val MAX_NODES = 800

class GraphViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = GraphRepository(SettingsRepository(application))

    private val _ui = MutableStateFlow(GraphUi())
    val ui: StateFlow<GraphUi> = _ui.asStateFlow()

    init {
        load()
    }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.load()
                .onSuccess { g ->
                    val laid = withContext(Dispatchers.Default) { layout3d(g) }
                    _ui.value = laid
                }
                .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message ?: "Sin conexión") } }
        }
    }

    /** Layout force-directed en 3D (Fruchterman–Reingold en el espacio), fuera del hilo
     *  principal. Si el vault supera MAX_NODES, se queda con los más conectados. */
    private fun layout3d(g: GraphResponse): GraphUi {
        val byId = g.nodes.associateBy { it.id }
        val degree = HashMap<String, Int>()
        for (e in g.edges) {
            if (e.source in byId && e.target in byId && e.source != e.target) {
                degree[e.source] = (degree[e.source] ?: 0) + 1
                degree[e.target] = (degree[e.target] ?: 0) + 1
            }
        }
        val kept = g.nodes.sortedByDescending { degree[it.id] ?: 0 }.take(MAX_NODES)
        val index = kept.mapIndexed { i, node -> node.id to i }.toMap()
        val n = kept.size
        if (n == 0) return GraphUi(loading = false)

        val edgePairs = g.edges.mapNotNull { e ->
            val a = index[e.source]; val b = index[e.target]
            if (a != null && b != null && a != b) a to b else null
        }.distinct()

        val x = DoubleArray(n); val y = DoubleArray(n); val z = DoubleArray(n)
        val spread = 560.0
        val rnd = java.util.Random(42)
        for (i in 0 until n) {
            x[i] = (rnd.nextDouble() - 0.5) * spread
            y[i] = (rnd.nextDouble() - 0.5) * spread
            z[i] = (rnd.nextDouble() - 0.5) * spread
        }
        val volume = spread * spread * spread
        val k = Math.cbrt(volume / n.coerceAtLeast(1))
        var temp = spread * 0.12
        // Menos iteraciones a más nodos, para que el cálculo siga siendo de pocos segundos.
        val iterations = if (n > 400) 220 else 320
        val dx = DoubleArray(n); val dy = DoubleArray(n); val dz = DoubleArray(n)

        repeat(iterations) {
            java.util.Arrays.fill(dx, 0.0); java.util.Arrays.fill(dy, 0.0); java.util.Arrays.fill(dz, 0.0)
            // repulsión 3D
            for (i in 0 until n) {
                for (j in i + 1 until n) {
                    var ax = x[i] - x[j]; var ay = y[i] - y[j]; var az = z[i] - z[j]
                    var dist = sqrt(ax * ax + ay * ay + az * az)
                    if (dist < 0.01) { dist = 0.01; ax = 0.01 }
                    val f = k * k / dist
                    val ux = ax / dist; val uy = ay / dist; val uz = az / dist
                    dx[i] += ux * f; dy[i] += uy * f; dz[i] += uz * f
                    dx[j] -= ux * f; dy[j] -= uy * f; dz[j] -= uz * f
                }
            }
            // atracción por aristas
            for ((a, b) in edgePairs) {
                var ax = x[a] - x[b]; var ay = y[a] - y[b]; var az = z[a] - z[b]
                var dist = sqrt(ax * ax + ay * ay + az * az)
                if (dist < 0.01) dist = 0.01
                val f = dist * dist / k
                val ux = ax / dist; val uy = ay / dist; val uz = az / dist
                dx[a] -= ux * f; dy[a] -= uy * f; dz[a] -= uz * f
                dx[b] += ux * f; dy[b] += uy * f; dz[b] += uz * f
            }
            // gravedad suave al centro
            for (i in 0 until n) {
                dx[i] -= x[i] * 0.02; dy[i] -= y[i] * 0.02; dz[i] -= z[i] * 0.02
            }
            // aplicar con tope por temperatura
            for (i in 0 until n) {
                val d = sqrt(dx[i] * dx[i] + dy[i] * dy[i] + dz[i] * dz[i])
                if (d > 0) {
                    val step = minOf(d, temp)
                    x[i] += dx[i] / d * step; y[i] += dy[i] / d * step; z[i] += dz[i] / d * step
                }
            }
            temp *= if (n > 400) 0.98 else 0.985
        }

        val nodes = kept.mapIndexed { i, node ->
            LaidNode(
                id = node.id,
                title = node.title.ifBlank { node.id },
                category = node.category,
                x = x[i].toFloat(),
                y = y[i].toFloat(),
                z = z[i].toFloat(),
                degree = degree[node.id] ?: 0,
            )
        }
        return GraphUi(nodes = nodes, edges = edgePairs, loading = false)
    }
}
