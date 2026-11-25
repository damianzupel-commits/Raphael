package com.raphael.empresas.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import com.raphael.empresas.app.AppViewModel
import com.raphael.empresas.app.Tab

@Composable
fun RaphaelApp(vm: AppViewModel) {
    if (!vm.loggedIn) LoginScreen(vm) else MainScreen(vm)
}

@Composable
fun LoginScreen(vm: AppViewModel) {
    var server by rememberSaveable(vm.pairHost) { mutableStateOf(vm.pairHost.ifBlank { vm.prefs.server }) }
    var key by remember { mutableStateOf("") }
    var code by remember(vm.pairCode) { mutableStateOf(vm.pairCode) }
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Raphael", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(8.dp))
        Text("Entrá con la dirección de tu Raphael y tu clave.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(server, { server = it }, label = { Text("Servidor") }, placeholder = { Text("https://tu-negocio.duckdns.org") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(key, { key = it }, label = { Text("Clave") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
        Spacer(Modifier.height(20.dp))
        Button(onClick = { vm.login(server, key); key = "" }, enabled = !vm.busy && server.isNotBlank() && key.isNotBlank(),
            modifier = Modifier.fillMaxWidth()) {
            if (vm.busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp) else Text("Entrar")
        }
        vm.message?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(20.dp))
        Text("Emparejar con un código", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
        Text("En la pantalla de Raphael (Configuración → Celular) sale un código y un QR. Escaneá el QR con la cámara y esta app se abre " +
            "con el código cargado, o escribilo acá. Vale 5 minutos y una sola vez.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(code, { code = it.uppercase() }, label = { Text("Código") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        Button(onClick = { vm.pair(server, code); code = "" }, enabled = !vm.busy && server.isNotBlank() && code.length >= 4,
            modifier = Modifier.fillMaxWidth()) { Text("Emparejar") }
        Spacer(Modifier.height(24.dp))
        Text("La clave se pone en el servidor. La app guarda solo la sesión, nunca la clave.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private data class TabSpec(val tab: Tab, val label: String, val icon: ImageVector)

private val TABS = listOf(
    TabSpec(Tab.HOY, "Hoy", Icons.Filled.Home),
    TabSpec(Tab.PENDIENTES, "Decidir", Icons.Filled.Notifications),
    TabSpec(Tab.ENCARGOS, "Encargos", Icons.Filled.List),
    TabSpec(Tab.AGENDA, "Agenda", Icons.Filled.DateRange),
    TabSpec(Tab.MAS, "Más", Icons.Filled.Menu),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(vm: AppViewModel) {
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(vm.message) {
        vm.message?.let {
            snack.showSnackbar(it)
            vm.message = null
        }
    }
    LaunchedEffect(vm.loggedIn) {                  // con la app abierta: pendientes y avisos al día
        while (vm.loggedIn) {
            delay(30_000)
            vm.quietRefresh()
        }
    }
    LaunchedEffect(vm.tab) {
        when (vm.tab) {
            Tab.PENDIENTES -> vm.loadPending()
            Tab.ENCARGOS -> vm.loadOrders()
            Tab.AGENDA -> vm.loadAgenda()
            Tab.MAS -> vm.loadMore()
            Tab.EQUIPO -> vm.loadPanel()
            Tab.CEREBRO -> vm.loadBrain()
            Tab.AJUSTES -> vm.loadConfig()
            Tab.HOY -> Unit
        }
    }
    Scaffold(
        topBar = {
            if (!vm.personal) TopAppBar(
                title = { Text(if (vm.personal) "Raphael" else vm.prefs.business.ifBlank { "Raphael Empresas" }) },
                actions = {
                    IconButton(onClick = {
                        when (vm.tab) {
                            Tab.HOY -> vm.ask("¿qué tareas tenemos hoy?")
                            Tab.PENDIENTES -> vm.loadPending()
                            Tab.ENCARGOS -> vm.loadOrders()
                            Tab.AGENDA -> vm.loadAgenda()
                            Tab.MAS -> vm.loadMore()
                            Tab.EQUIPO -> vm.loadPanel()
                            Tab.CEREBRO -> vm.loadBrain()
                            Tab.AJUSTES -> vm.loadConfig()
                        }
                    }) { Icon(Icons.Filled.Refresh, contentDescription = "Actualizar") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        bottomBar = {
            if (!vm.personal) NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                TABS.forEach { t ->
                    NavigationBarItem(
                        selected = vm.tab == t.tab,
                        onClick = { vm.tab = t.tab },
                        label = { Text(t.label) },
                        icon = {
                            val n = when (t.tab) {
                                Tab.PENDIENTES -> vm.pending.size
                                Tab.MAS -> vm.unseenNotices
                                else -> 0
                            }
                            if (n > 0) BadgedBox(badge = { Badge { Text("$n") } }) { Icon(t.icon, t.label) } else Icon(t.icon, t.label)
                        },
                    )
                }
            }
        },
        snackbarHost = { SnackbarHost(snack) },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            if (vm.personal) PersonalHome(vm) else when (vm.tab) {
                Tab.HOY -> TodayScreen(vm)
                Tab.PENDIENTES -> PendingScreen(vm)
                Tab.ENCARGOS -> OrdersScreen(vm)
                Tab.AGENDA -> AgendaScreen(vm)
                Tab.MAS -> MoreScreen(vm)
                Tab.EQUIPO, Tab.CEREBRO -> BrainScreen(vm)
                Tab.AJUSTES -> SettingsScreen(vm)
            }
            if (vm.busy) LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter))
            vm.conversation?.let { (contact, lines) -> ConversationDialog(contact, lines) { vm.conversation = null } }
        }
    }
}
