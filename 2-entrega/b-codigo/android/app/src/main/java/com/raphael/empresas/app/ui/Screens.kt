package com.raphael.empresas.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.raphael.empresas.app.AppViewModel
import com.raphael.empresas.app.Appointment
import com.raphael.empresas.app.ChatEntry
import com.raphael.empresas.app.ChatLine
import com.raphael.empresas.app.Order
import com.raphael.empresas.app.Pending
import com.raphael.empresas.app.money
import com.raphael.empresas.app.shortDate

// --- Hoy: la Secretaria ----------------------------------------------------------------------------------------------
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TodayScreen(vm: AppViewModel) {
    var text by remember { mutableStateOf("") }
    val state = rememberLazyListState()
    LaunchedEffect(vm.chat.size) { if (vm.chat.isNotEmpty()) state.animateScrollToItem(vm.chat.size - 1) }
    Column(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp), state = state,
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Spacer(Modifier.height(8.dp)) }
            items(vm.chat) { e -> Bubble(e, onAsk = { vm.ask(it) }) }
            item {
                val last = vm.chat.lastOrNull()
                if (last != null && !last.fromOwner && last.suggestions.isNotEmpty()) {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        last.suggestions.forEach { s -> AssistChip(onClick = { vm.ask(s) }, label = { Text(s) }) }
                    }
                }
                Spacer(Modifier.height(8.dp))
            }
        }
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(text, { text = it }, modifier = Modifier.weight(1f), placeholder = { Text(if (vm.personal) "Decile algo a Raphael" else "Decile algo a tu secretaria") },
                maxLines = 4)
            IconButton(onClick = { if (text.isNotBlank()) vm.ask(text.trim()); text = "" }, enabled = !vm.busy) {
                Icon(Icons.Filled.Send, "Mandar", tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@Composable
private fun Bubble(e: ChatEntry, onAsk: (String) -> Unit) {
    val mine = e.fromOwner
    Box(Modifier.fillMaxWidth(), contentAlignment = if (mine) Alignment.CenterEnd else Alignment.CenterStart) {
        Column(
            Modifier.widthIn(max = 320.dp)
                .background(if (mine) MaterialTheme.colorScheme.primary.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surface,
                    RoundedCornerShape(14.dp))
                .padding(12.dp),
        ) {
            if (e.tasks.isEmpty()) Text(e.text) else Text(e.text.substringBefore("\n1)").ifBlank { "Tareas de hoy:" })
            e.tasks.forEach { t ->
                Spacer(Modifier.height(6.dp))
                Card(Modifier.fillMaxWidth().clickable { onAsk("contame la ${t.id}") },
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                    Column(Modifier.padding(10.dp)) {
                        Text("${t.id}) ${t.title}", fontWeight = FontWeight.SemiBold)
                        if (t.reason.isNotBlank()) Text(t.reason, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            e.options.forEachIndexed { i, o ->
                Spacer(Modifier.height(4.dp))
                Text("${'A' + i}. ${o.title}" + if (o.recommended) "  ·  lo que yo haría" else "",
                    fontWeight = if (o.recommended) FontWeight.SemiBold else FontWeight.Normal)
                Text(o.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

// --- Decidir: pendientes ---------------------------------------------------------------------------------------------
private val FIELD_LABELS = mapOf("price" to "Precio", "amount" to "Monto", "date" to "Fecha (AAAA-MM-DD)", "time" to "Hora (HH:MM)")

@Composable
fun PendingScreen(vm: AppViewModel) {
    var approving by remember { mutableStateOf<Pending?>(null) }
    var rejecting by remember { mutableStateOf<Pending?>(null) }
    var resolving by remember { mutableStateOf<Pending?>(null) }
    if (vm.pending.isEmpty()) {
        Empty("No hay nada esperando tu decisión.")
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(vm.pending, key = { it.id }) { p ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(p.title, fontWeight = FontWeight.Bold, color = if (p.human) Warn else MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.weight(1f))
                            Text("#${p.id}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(p.summary)
                        p.contact?.let { c ->
                            TextButton(onClick = { vm.openConversation(c) }) { Text("Ver la conversación") }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if ("resolve" in p.can) {
                                Button(onClick = { resolving = p }) { Text("Responder") }
                            }
                            if ("approve" in p.can) {
                                Button(onClick = { approving = p }) { Text("Aprobar") }
                                OutlinedButton(onClick = { rejecting = p }) { Text("Rechazar") }
                            }
                        }
                    }
                }
            }
        }
    }
    approving?.let { p -> ApproveDialog(p, onDismiss = { approving = null }) { changes -> vm.approve(p, changes); approving = null } }
    rejecting?.let { p ->
        TextDialog("Rechazar", "¿Por qué? (opcional, queda anotado)", "Rechazar", required = false,
            onDismiss = { rejecting = null }) { vm.reject(p, it); rejecting = null }
    }
    resolving?.let { p ->
        TextDialog("Responder", "Lo que le mando al cliente (vacío = lo marco resuelto sin escribirle)", "Mandar",
            required = false, onDismiss = { resolving = null }) { vm.resolve(p, it); resolving = null }
    }
}

@Composable
private fun ApproveDialog(p: Pending, onDismiss: () -> Unit, onConfirm: (Map<String, Any>) -> Unit) {
    val values = remember { mutableStateMapOf<String, String>().apply {
        p.editable.forEach { f -> put(f, p.data.opt(f)?.takeIf { it != org.json.JSONObject.NULL }?.let {
            if (it is Number) it.toLong().toString() else it.toString() } ?: "") }
    } }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("¿Confirmás?") },
        text = {
            Column {
                Text(p.summary)
                p.editable.forEach { f ->
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(values[f] ?: "", { values[f] = it }, label = { Text(FIELD_LABELS[f] ?: f) }, singleLine = true)
                }
                if (p.type == "enviar_presupuesto" || p.type == "confirmar_pago") {
                    Spacer(Modifier.height(8.dp))
                    Text("Esto no tiene vuelta atrás: el cliente recibe el mensaje.", color = Warn,
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                val changes = mutableMapOf<String, Any>()
                p.editable.forEach { f ->
                    val v = (values[f] ?: "").trim()
                    val orig = p.data.opt(f)?.toString() ?: ""
                    if (v.isNotEmpty() && v != orig && !(v.toDoubleOrNull() != null && v.toDoubleOrNull() == orig.toDoubleOrNull())) {
                        changes[f] = if (f == "price" || f == "amount") (v.replace(".", "").replace(",", ".").toDoubleOrNull() ?: v) else v
                    }
                }
                onConfirm(changes)
            }) { Text("Sí, aprobar") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
fun TextDialog(title: String, hint: String, action: String, required: Boolean, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { OutlinedTextField(text, { text = it }, placeholder = { Text(hint) }, minLines = 2) },
        confirmButton = { Button(onClick = { onConfirm(text.trim()) }, enabled = !required || text.isNotBlank()) { Text(action) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

// --- Encargos ---------------------------------------------------------------------------------------------------------
@Composable
fun OrdersScreen(vm: AppViewModel) {
    var confirm by remember { mutableStateOf<Pair<Order, String>?>(null) }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = !vm.showAllOrders, onClick = { vm.showAllOrders = false; vm.loadOrders() }, label = { Text("En curso") })
            FilterChip(selected = vm.showAllOrders, onClick = { vm.showAllOrders = true; vm.loadOrders() }, label = { Text("Todos") })
        }
        if (vm.orders.isEmpty()) Empty("No hay encargos ${if (vm.showAllOrders) "" else "en curso"}.")
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(vm.orders, key = { it.number }) { o -> OrderCard(o, onContact = { vm.openConversation(it) }) { confirm = o to it } }
            item { Spacer(Modifier.height(12.dp)) }
        }
    }
    confirm?.let { (o, s) ->
        AlertDialog(
            onDismissRequest = { confirm = null },
            title = { Text("¿Confirmás?") },
            text = { Text("El encargo #${o.number} de ${o.client} pasa a «${Order.STATUS_NAMES[s]}». Si llegó por WhatsApp o Instagram, el cliente recibe el aviso.") },
            confirmButton = { Button(onClick = { vm.setStatus(o, s); confirm = null }) { Text("Sí, cambiar") } },
            dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancelar") } },
        )
    }
}

@Composable
private fun OrderCard(o: Order, onContact: (String) -> Unit, onStatus: (String) -> Unit) {
    var menu by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("#${o.number} · ${o.client}", fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                if (o.urgent) Text("URGENTE", color = Warn, style = MaterialTheme.typography.labelSmall)
            }
            Text(o.description)
            Spacer(Modifier.height(4.dp))
            Text("Entrega: ${shortDate(o.due)} · ${Order.STATUS_NAMES[o.status] ?: o.status}",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            if (o.price != null) {
                Text("Precio ${money(o.price)} · seña ${money(o.deposit)} · pagado ${money(o.paid)}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            if (o.measures.isNotBlank()) Text("Medidas: ${o.measures}", style = MaterialTheme.typography.bodySmall)
            Row {
                o.contact?.let { c -> TextButton(onClick = { onContact(c) }) { Text("Conversación") } }
                Spacer(Modifier.weight(1f))
                if (o.status !in listOf("presupuesto", "entregado", "cancelado")) {
                    Box {
                        TextButton(onClick = { menu = true }) { Text("Cambiar estado") }
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            Order.SETTABLE.filter { it != o.status }.forEach { s ->
                                DropdownMenuItem(text = { Text(Order.STATUS_NAMES[s] ?: s) }, onClick = { menu = false; onStatus(s) })
                            }
                        }
                    }
                }
            }
        }
    }
}

// --- Agenda -----------------------------------------------------------------------------------------------------------
@Composable
fun AgendaScreen(vm: AppViewModel) {
    if (vm.appointments.isEmpty()) {
        Empty("No hay turnos confirmados de hoy en adelante.")
        return
    }
    val byDate: Map<String, List<Appointment>> = vm.appointments.groupBy { it.date }
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        byDate.forEach { (d, list) ->
            item { Text(shortDate(d), fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 8.dp)) }
            items(list) { a ->
                Card(Modifier.fillMaxWidth().clickable(enabled = a.contact != null) { a.contact?.let { vm.openConversation(it) } }) {
                    Row(Modifier.padding(12.dp)) {
                        Text(a.time, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(56.dp))
                        Text("${a.reason} · ${a.name.ifBlank { a.contact ?: "" }}")
                    }
                }
            }
        }
    }
}

// --- Más --------------------------------------------------------------------------------------------------------------
@Composable
fun MoreScreen(vm: AppViewModel) {
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Section("Avisos") }
        if (vm.notices.isEmpty()) item { Muted("Ninguno.") }
        items(vm.notices.take(15), key = { it.id }) { n ->
            Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(
                containerColor = if (n.failedSend) Warn.copy(alpha = 0.15f) else MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(10.dp)) {
                    Text(n.text, fontWeight = if (n.seen) FontWeight.Normal else FontWeight.SemiBold)
                    Text(n.time.replace('T', ' '), style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item { Section("WhatsApp e Instagram") }
        item {
            val ch = vm.channels
            Muted(when {
                ch == null -> "…"
                ch.mode.isBlank() -> ch.problems.firstOrNull() ?: "Sin canal configurado."
                !ch.real -> "En modo prueba: no se le manda nada a los clientes (${ch.channels.joinToString()})."
                else -> "Andando: ${ch.channels.joinToString()}."
            })
        }
        vm.channels?.problems?.let { ps -> items(ps) { p -> Text("• $p", color = Warn) } }
        item { Section("Señas esperando") }
        if (vm.depositsWaiting.isEmpty()) item { Muted("Ninguna.") }
        items(vm.depositsWaiting) { d -> Muted("#${d.number} · ${d.client} · ${money(d.deposit)} · desde ${shortDate(d.since)}") }
        if (vm.depositsNotified.isNotEmpty()) {
            item { Section("Avisaron que pagaron (confirmalo en Decidir)") }
            items(vm.depositsNotified) { d -> Muted("#${d.number} · ${d.client} · ${money(d.deposit)}") }
        }
        item { Section("Preguntas que el bot no supo responder") }
        val open = vm.questions.filter { it.status == "abierta" }
        if (open.isEmpty()) item { Muted("Ninguna abierta.") }
        items(open) { q -> Muted("«${q.question}»") }
        item { Section("Catálogo de la tienda") }
        item {
            val st = vm.catalogState
            Muted(when {
                st == null -> "…"
                !st.configured -> "Sin catálogo configurado (se pone en la instalación: store.source.url)."
                st.error.isNotBlank() -> "No se está actualizando: ${st.error}. Última copia buena: ${st.lastOk.ifBlank { "nunca" }}."
                else -> "${st.count} productos · actualizado ${st.lastOk.replace('T', ' ')}"
            })
        }
        items(vm.products.take(50)) { p ->
            Muted("${p.title} · ${money(p.price)}" + (p.stock?.let { " · stock $it" } ?: ""))
        }
        item {
            HorizontalDivider(Modifier.padding(vertical = 12.dp))
            Muted("Conectada a ${vm.prefs.server} como ${vm.prefs.user}")
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.logout() }) { Text("Cerrar sesión") }
        }
    }
}

@Composable
fun ConversationDialog(contact: String, lines: List<ChatLine>, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(contact) },
        text = {
            LazyColumn(Modifier.height(380.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(lines) { l ->
                    Column(Modifier.fillMaxWidth().background(
                        if (l.fromClient) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                        RoundedCornerShape(10.dp)).padding(8.dp)) {
                        Text(if (l.fromClient) "Cliente" else "Raphael", style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(l.text)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Cerrar") } },
    )
}

@Composable
private fun Section(t: String) = Text(t, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary,
    modifier = Modifier.padding(top = 10.dp))

@Composable
private fun Muted(t: String) = Text(t, color = MaterialTheme.colorScheme.onSurfaceVariant)

@Composable
fun Empty(t: String) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(t, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
