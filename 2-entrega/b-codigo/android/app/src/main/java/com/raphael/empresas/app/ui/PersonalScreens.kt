package com.raphael.empresas.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.raphael.empresas.app.AppViewModel
import com.raphael.empresas.app.CheckItem
import com.raphael.empresas.app.ConfigField

// --- Raphael personal: Cerebro y Ajustes -------------------------------------------------------------------------------

/** Qué modelo usa cada rol y si el modelo local está prendido. Solo mira: los cambios se hacen en Ajustes. */
@Composable
fun BrainScreen(vm: AppViewModel) {
    val b = vm.brain
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (b == null) {
            item { Text("…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            return@LazyColumn
        }
        item {
            Text(
                if (b.localReady) "Modelo local prendido: lo privado corre en tu PC." else
                    "Sin modelo local: lo privado va por reglas y no sale a la nube.",
                fontWeight = FontWeight.SemiBold, color = if (b.localReady) MaterialTheme.colorScheme.primary else Warn)
        }
        items(b.hints) { h -> Text("• $h", color = Warn) }
        item { Heading("Solo local") }
        item { Text(b.privateBrigades.joinToString(", ").ifBlank { "ninguna" }, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        item { Heading("Qué usa cada rol") }
        items(b.roles) { r ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(10.dp)) {
                    Text(r.role, fontWeight = FontWeight.SemiBold)
                    Text(r.tiers.joinToString(" → ") + if (r.now.isNotBlank()) "  (${r.now})" else "",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Configuración del servidor: claves y roles a voluntad. Los secretos se escriben y se mandan; nunca vuelven completos. */
@Composable
fun SettingsScreen(vm: AppViewModel) {
    val c = vm.config
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (c == null) {
            item { Text("…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            return@LazyColumn
        }
        item { Heading("Estado") }
        items(c.checks) { CheckRow(it) }
        if (c.restartNeeded.isNotEmpty()) {
            item { Text("Hay que reiniciar Raphael para: ${c.restartNeeded.joinToString()}", color = Warn) }
        }
        val groups = c.fields.groupBy { it.group }
        GROUP_TITLES.forEach { (key, title) ->
            val fs = groups[key].orEmpty()
            if (fs.isNotEmpty()) {
                item { Heading(title) }
                items(fs, key = { it.name }) { f -> FieldRow(f, onSave = { v -> vm.saveConfig(mapOf(f.name to v)) },
                    onClear = { vm.saveConfig(emptyMap(), listOf(f.name)) }) }
            }
        }
        item {
            HorizontalDivider(Modifier.padding(vertical = 12.dp))
            Text("Conectada a ${vm.prefs.server} como ${vm.prefs.user}", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { vm.logout() }) { Text("Cerrar sesión") }
        }
    }
}

private val GROUP_TITLES = listOf("ia" to "IA en la nube", "local" to "Modelo local", "roles" to "Modelo de cada rol",
    "red" to "Celular", "voz" to "Voz", "cuentas" to "Otras cuentas")

@Composable
private fun Heading(t: String) = Text(t, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary,
    modifier = Modifier.padding(top = 10.dp))

@Composable
private fun CheckRow(i: CheckItem) {
    val mark = when (i.status) { "ok" -> "✔"; "falta" -> "✖"; "aviso" -> "▲"; else -> "•" }
    val color = when (i.status) {
        "ok" -> MaterialTheme.colorScheme.primary
        "falta" -> MaterialTheme.colorScheme.error
        "aviso" -> Warn
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text("$mark ${i.area}: ${i.text}", color = color, style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun FieldRow(f: ConfigField, onSave: (String) -> Unit, onClear: () -> Unit) {
    var v by remember(f.name, f.value, f.set) { mutableStateOf(if (f.secret) "" else f.value) }
    Column(Modifier.fillMaxWidth()) {
        OutlinedTextField(v, { v = it }, modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text(f.label) },
            placeholder = { Text(if (f.set && f.secret) "cargada ${f.hint} · escribí para reemplazarla" else "sin cargar") },
            supportingText = if (f.help.isNotBlank()) ({ Text(f.help) }) else null,
            visualTransformation = if (f.secret) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
            keyboardOptions = KeyboardOptions(keyboardType = if (f.secret) KeyboardType.Password else KeyboardType.Text))
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { onSave(v.trim()) }, enabled = v.isNotBlank() && v.trim() != f.value) { Text("Guardar") }
            if (f.set) TextButton(onClick = onClear) { Text("Quitar") }
        }
    }
}
