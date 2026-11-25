package com.raphael.empresas.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.raphael.empresas.app.AppViewModel
import com.raphael.empresas.app.BrigadeInfo
import com.raphael.empresas.app.Looks
import com.raphael.empresas.app.PanelData
import com.raphael.empresas.app.Tab
import com.raphael.empresas.app.isBad
import com.raphael.empresas.app.spaced
import kotlinx.coroutines.launch

// --- El panel de la PC, adaptado al celular ----------------------------------------------------------------------------
// Arriba: la esfera y el título; la fila de brigadas (el orquestador y las montadas); "Estado y tareas". Abajo, secciones que
// se deslizan: Hablar, Decidir, Equipo (cocineros, efímeros y herramientas), Núcleo y ☰ Configuración.

private class Page(val tab: Tab, val label: String)

private val PAGES = listOf(
    Page(Tab.HOY, "Hablar"), Page(Tab.PENDIENTES, "Decidir"), Page(Tab.EQUIPO, "Equipo"),
    Page(Tab.CEREBRO, "⚙ Núcleo"), Page(Tab.AJUSTES, "☰ Configuración"),
)

@Composable
fun PersonalHome(vm: AppViewModel) {
    val pager = rememberPagerState(initialPage = PAGES.indexOfFirst { it.tab == vm.tab }.coerceAtLeast(0), pageCount = { PAGES.size })
    val scope = rememberCoroutineScope()
    fun go(tab: Tab) {
        val i = PAGES.indexOfFirst { it.tab == tab }
        if (i >= 0) scope.launch { pager.animateScrollToPage(i) }
    }
    // El que se desliza manda: la pestaña del modelo sigue a la página (y carga lo suyo).
    LaunchedEffect(pager.currentPage) { vm.tab = PAGES[pager.currentPage].tab }
    LaunchedEffect(vm.tab) { if (PAGES[pager.currentPage].tab != vm.tab) go(vm.tab) }

    Column(Modifier.fillMaxSize()) {
        PanelHeader(onOrb = { vm.scope = null; go(Tab.HOY) })
        BrigadeRow(vm, onPick = { vm.scope = it; go(if (it == null) Tab.HOY else Tab.EQUIPO) })
        StatusCard(vm, onDecide = { go(Tab.PENDIENTES) })
        SectionTabs(pager.currentPage, vm.pending.size) { i -> scope.launch { pager.animateScrollToPage(i) } }
        HorizontalPager(pager, Modifier.weight(1f).fillMaxWidth(), beyondViewportPageCount = 1) { i ->
            when (PAGES[i].tab) {
                Tab.HOY -> TodayScreen(vm)
                Tab.PENDIENTES -> PendingScreen(vm)
                Tab.EQUIPO -> TeamScreen(vm)
                Tab.CEREBRO -> NucleoScreen(vm)
                else -> SettingsScreen(vm)
            }
        }
    }
}

/** La esfera brillante del encabezado: halo cian difuso y núcleo con degradé y brillo arriba a la izquierda. */
@Composable
fun Orb(size: Int, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size.dp)) {
        val c = center
        val r = this.size.minDimension
        drawCircle(Brush.radialGradient(listOf(Color(0x9636DAFD), Color(0x0036DAFD)), center = c, radius = r * 0.5f),
            radius = r * 0.5f, center = c)
        val core = r * 0.24f
        drawCircle(Brush.radialGradient(
            listOf(Color(0xFFEEFBFD), Color(0xFF36DAFD), Color(0xFF1F78FD)),
            center = Offset(c.x - core * 0.25f, c.y - core * 0.3f), radius = core * 1.25f), radius = core, center = c)
    }
}

@Composable
private fun PanelHeader(onOrb: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Orb(52, Modifier.clickable(onClick = onOrb))
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text("RAPHAEL · HARNESS V2", color = TextMain, fontWeight = FontWeight.Bold, fontSize = 15.sp, letterSpacing = 2.sp,
                maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.clickable(onClick = onOrb))
            Text("TOCÁ LA ESFERA PARA EL ORQUESTADOR", color = Muted, fontSize = 8.sp, letterSpacing = 1.sp, maxLines = 1)
        }
    }
}

/** El orquestador y las brigadas montadas, como tarjetitas que se deslizan. La elegida se ilumina. */
@Composable
private fun BrigadeRow(vm: AppViewModel, onPick: (String?) -> Unit) {
    val p = vm.panel
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        BrigadeChip("Orquestador", "todas las brigadas", Looks.orchestrator.icon, Color(Looks.orchestrator.color), vm.scope == null) { onPick(null) }
        p?.mounted?.forEach { b ->
            val look = Looks.of(b.id)
            BrigadeChip(b.name, if (b.private) "solo local" else "${b.cooks.size} cocineros", look.icon, Color(look.color),
                vm.scope == b.id) { onPick(b.id) }
        }
    }
}

@Composable
private fun BrigadeChip(name: String, sub: String, icon: String, color: Color, selected: Boolean, onClick: () -> Unit) {
    val shape = RoundedCornerShape(12.dp)
    Row(Modifier.width(150.dp).background(if (selected) ActiveBg else NightCard, shape)
        .border(BorderStroke(1.dp, if (selected) Cyan else CardBorder), shape)
        .clickable(onClick = onClick).padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Text(icon, color = color, fontSize = 18.sp)
        Spacer(Modifier.width(8.dp))
        Column {
            Text(name, color = TextMain, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(sub, color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** "Estado y tareas": cuántas brigadas, qué corre ahora y qué espera a una persona. Tocar lo que espera lleva a Decidir. */
@Composable
private fun StatusCard(vm: AppViewModel, onDecide: () -> Unit) {
    val all = vm.panel
    val p = all?.scoped(vm.scope)
    val shape = RoundedCornerShape(14.dp)
    var open by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp).background(NightCard, shape)
        .border(BorderStroke(1.dp, CardBorder), shape).clickable { open = !open }.padding(horizontal = 12.dp, vertical = 8.dp)) {
        Row {
            Text(spaced("Estado y tareas"), color = Muted, fontWeight = FontWeight.Bold, fontSize = 8.sp, modifier = Modifier.weight(1f))
            val label = vm.scope?.let { id -> all?.brigades?.firstOrNull { it.id == id }?.name } ?: "en vivo"
            Text("● $label", color = Good, fontWeight = FontWeight.Bold, fontSize = 10.sp, maxLines = 1)
        }
        Spacer(Modifier.height(4.dp))
        if (p == null) {
            Text("Conectando…", color = Muted, fontSize = 12.sp)
            return
        }
        val first = if (vm.scope == null) "${p.mounted.size} brigada${if (p.mounted.size != 1) "s" else ""}" else
            "${p.brigades.firstOrNull()?.cooks?.size ?: 0} cocineros"
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("$first  ·  ${p.running} en curso  ·  ", color = TextMain, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            Text("${p.toApprove} por aprobar", color = if (p.toApprove > 0) Warn else TextMain, fontWeight = FontWeight.Bold, fontSize = 12.sp)
        }
        if (all.down > 0) Text("⚡ ${all.down} pieza${if (all.down != 1) "s" else ""} caída${if (all.down != 1) "s" else ""}",
            color = Bad, fontWeight = FontWeight.Bold, fontSize = 12.sp)
        if (p.tasks.isEmpty()) {
            Text(if (p.mounted.isEmpty()) "Sin tareas: no hay brigadas trabajando." else "Sin tareas en este momento.", color = Dim, fontSize = 11.sp)
        }
        val order = listOf("aprobación", "te toca a vos", "en curso")
        val shown = p.tasks.sortedBy { order.indexOf(it.state).let { i -> if (i < 0) 9 else i } }
        shown.take(if (open) 8 else 1).forEach { t ->
            val color = if (t.state == "en curso") Cyan else Warn
            Row(Modifier.fillMaxWidth().clickable(enabled = t.pending != null, onClick = onDecide).padding(vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Text("●", color = color, fontSize = 8.sp)
                Spacer(Modifier.width(6.dp))
                Text(t.title, color = TextMain, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                Spacer(Modifier.width(6.dp))
                Text(if (t.pending != null) "${t.state} ›" else t.state, color = color, fontWeight = FontWeight.Bold, fontSize = 10.sp)
            }
        }
        if (shown.size > 1) Text(if (open) "▲ menos" else "▼ ${shown.size - 1} más", color = Muted, fontSize = 10.sp)
    }
}

/** Las secciones, como píldoras que se deslizan y siguen a la página. */
@Composable
private fun SectionTabs(current: Int, pending: Int, onPick: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        PAGES.forEachIndexed { i, pg ->
            val on = i == current
            val shape = RoundedCornerShape(12.dp)
            Box(Modifier.background(if (on) ActiveBg else Color.Transparent, shape)
                .border(BorderStroke(1.dp, if (on) Cyan else PanelBorder), shape)
                .clickable { onPick(i) }.padding(horizontal = 14.dp, vertical = 7.dp), contentAlignment = Alignment.Center) {
                Text(if (pg.tab == Tab.PENDIENTES && pending > 0) "${pg.label} · $pending" else pg.label, color = if (on) Cyan else Muted, fontWeight = if (on) FontWeight.Bold else FontWeight.Normal, fontSize = 13.sp)
            }
        }
    }
}

// --- Equipo: cocineros, efímeros, herramientas -------------------------------------------------------------------------
@Composable
fun TeamScreen(vm: AppViewModel) {
    val p = vm.panel?.scoped(vm.scope)
    if (p == null) {
        Empty("Cargando el equipo…")
        return
    }
    val cooks = p.mounted.flatMap { b -> b.cooks.map { c -> Triple(c.id, b.name, c.state) } }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Spacer(Modifier.height(2.dp)) }
        item {
            PanelBox("Cocineros permanentes") {
                if (cooks.isEmpty()) EmptyLine("Ninguna brigada montada con cocineros.")
                cooks.forEach { (c, b, st) -> DataRow(c, b, st, if (isBad(st)) Bad else if (st == "en espera" || st == "listo") Muted else Cyan) }
            }
        }
        item {
            PanelBox("Ayudantes efímeros") {
                if (p.ephemerals.isEmpty()) EmptyLine("Ninguno trabajando ahora.")
                p.ephemerals.forEach { e -> DataRow(e.helper, "${e.brigade} · ${e.task}".trim(' ', '·'), e.time, Cyan) }
            }
        }
        item {
            PanelBox("Herramientas de uso compartido") {
                if (p.tools.isEmpty()) EmptyLine("Sin herramientas registradas.")
                p.tools.forEach { t ->
                    DataRow(t.name, "${t.owner} · nivel ${t.level}", if (t.enabled) "activa" else "apagada", if (t.enabled) Good else Dim)
                }
            }
        }
        item { Spacer(Modifier.height(12.dp)) }
    }
}

@Composable
private fun PanelBox(title: String, content: @Composable () -> Unit) {
    val shape = RoundedCornerShape(14.dp)
    Column(Modifier.fillMaxWidth().background(NightPanel, shape).border(BorderStroke(1.dp, PanelBorder), shape).padding(12.dp)) {
        Text(spaced(title), color = Muted, fontWeight = FontWeight.Bold, fontSize = 8.sp)
        Spacer(Modifier.height(6.dp))
        content()
    }
}

@Composable
private fun EmptyLine(t: String) = Text(t, color = Dim, fontSize = 12.sp, modifier = Modifier.padding(vertical = 4.dp))

@Composable
private fun DataRow(title: String, sub: String, state: String, color: Color) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).background(color, CircleShape))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = TextMain, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (sub.isNotBlank()) Text(sub, color = Muted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Text(state, color = color, fontWeight = FontWeight.Bold, fontSize = 11.sp)
    }
}

// --- Núcleo: contadores, brigadas encontradas y el cerebro ----------------------------------------------------------------
@Composable
fun NucleoScreen(vm: AppViewModel) {
    val p = vm.panel
    Column(Modifier.fillMaxSize()) {
        if (p != null) {
            Text("Contrato del núcleo ${p.contract} · ${p.edition}", color = Cyan, fontWeight = FontWeight.Bold, fontSize = 11.sp,
                modifier = Modifier.padding(start = 14.dp, bottom = 6.dp))
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Tile("Brigadas", "${p.mounted.size}", Modifier.weight(1f))
                Tile("Caídas", "${p.down}", Modifier.weight(1f), if (p.down > 0) Bad else TextMain)
                Tile("Por decidir", "${vm.pending.size}", Modifier.weight(1f), if (vm.pending.isNotEmpty()) Warn else TextMain)
            }
            Spacer(Modifier.height(8.dp))
            FoundBrigades(p.brigades)
        }
        Box(Modifier.weight(1f)) { BrainScreen(vm) }
    }
}

@Composable
private fun Tile(label: String, value: String, modifier: Modifier, color: Color = TextMain) {
    val shape = RoundedCornerShape(12.dp)
    Column(modifier.background(NightCard, shape).border(BorderStroke(1.dp, CardBorder), shape).padding(10.dp)) {
        Text(label.uppercase(), color = Muted, fontWeight = FontWeight.Bold, fontSize = 8.sp, letterSpacing = 1.sp, maxLines = 1)
        Text(value, color = color, fontWeight = FontWeight.Bold, fontSize = 22.sp)
    }
}

@Composable
private fun FoundBrigades(all: List<BrigadeInfo>) {
    val shape = RoundedCornerShape(14.dp)
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp).background(NightPanel, shape)
        .border(BorderStroke(1.dp, PanelBorder), shape).padding(12.dp)) {
        Text(spaced("Brigadas encontradas"), color = Muted, fontWeight = FontWeight.Bold, fontSize = 8.sp)
        Spacer(Modifier.height(6.dp))
        Column(Modifier.horizontalScroll(rememberScrollState())) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                all.forEach { b ->
                    val look = Looks.of(b.id)
                    val on = b.mounted
                    Row(Modifier.background(if (on) ActiveBg else InputBg, RoundedCornerShape(10.dp)).padding(horizontal = 10.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text(look.icon, color = if (on) Color(look.color) else Dim, fontSize = 14.sp)
                        Spacer(Modifier.width(6.dp))
                        Text(b.name, color = if (on) TextMain else Dim, fontSize = 12.sp)
                        if (!on) Text("  sin montar", color = Dim, fontSize = 10.sp)
                    }
                }
            }
        }
    }
}
