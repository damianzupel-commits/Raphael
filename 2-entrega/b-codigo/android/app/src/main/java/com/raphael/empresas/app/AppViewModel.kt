package com.raphael.empresas.app

import android.app.Application
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

/** Una burbuja del chat con la Secretaria. */
data class ChatEntry(val fromOwner: Boolean, val text: String, val tasks: List<TaskItem> = emptyList(),
                     val options: List<OptionItem> = emptyList(), val suggestions: List<String> = emptyList())

enum class Tab { HOY, PENDIENTES, ENCARGOS, AGENDA, MAS, EQUIPO, CEREBRO, AJUSTES }

/**
 * El estado de la app. Toda decisión (aprobar, rechazar, resolver, cambiar un estado) va al servidor, que la pasa por
 * el Policy Engine del harness: la app no decide nada por su cuenta y no guarda datos de clientes.
 */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)

    var loggedIn by mutableStateOf(prefs.loggedIn)
        private set
    var busy by mutableStateOf(false)
        private set
    /** Solo el chat: mientras espera una respuesta del orquestador. Aparte de `busy` para que una carga lenta de fondo no deje el botón Enviar gris. */
    var chatting by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)
    var tab by mutableStateOf(Tab.HOY)

    /** "empresas" o "personal": cambia las pestañas y a qué endpoint se le habla. */
    var edition by mutableStateOf(prefs.edition)
        private set
    val personal get() = edition == "personal"
    /** Lo que trajo el QR (o se escribió a mano) para emparejar: la pantalla de entrada lo muestra ya cargado. */
    var pairHost by mutableStateOf("")
    var pairCode by mutableStateOf("")
    var brain by mutableStateOf<Brain?>(null)
        private set
    var panel by mutableStateOf<PanelData?>(null)
        private set
    /** Brigada elegida en la fila de chips (null = el orquestador, o sea todas). */
    var scope by mutableStateOf<String?>(null)
    var config by mutableStateOf<ConfigView?>(null)
        private set

    var summary by mutableStateOf<Summary?>(null)
        private set
    val pending = mutableStateListOf<Pending>()
    val orders = mutableStateListOf<Order>()
    var showAllOrders by mutableStateOf(false)
    val appointments = mutableStateListOf<Appointment>()
    val depositsWaiting = mutableStateListOf<Deposit>()
    val depositsNotified = mutableStateListOf<Deposit>()
    val questions = mutableStateListOf<Question>()
    var catalogState by mutableStateOf<CatalogState?>(null)
        private set
    val products = mutableStateListOf<Product>()
    val chat = mutableStateListOf<ChatEntry>()
    var conversation by mutableStateOf<Pair<String, List<ChatLine>>?>(null)
    val notices = mutableStateListOf<Notice>()
    var unseenNotices by mutableStateOf(0)
        private set
    var channels by mutableStateOf<Channels?>(null)
        private set

    private fun run(block: suspend () -> Unit) {
        viewModelScope.launch {
            busy = true
            try {
                block()
            } catch (e: ApiError) {
                onApiError(e)
            } finally {
                busy = false
            }
        }
    }

    private fun onApiError(e: ApiError) {
        if (e.unauthorized) {
            prefs.clearSession()
            loggedIn = false
        }
        message = e.message
    }

    // --- sesión
    fun login(server: String, key: String) = run {
        val url = normalizeServer(server)
        if (url.isBlank()) throw ApiError("Poné la dirección del servidor", 0)
        val api = Api(url)
        val h = api.health()
        if (!h.optBoolean("ok")) throw ApiError("Ese servidor no tiene Raphael funcionando", 0)
        val s = api.login(key, deviceName())
        startSession(url, h.optString("edition"), s)
    }

    /** Emparejar con el código del QR (sin clave). Desde afuera de casa el servidor sigue pidiendo clave o código: nunca entra solo. */
    fun pair(server: String, code: String) = run {
        val url = normalizeServer(server)
        if (url.isBlank()) throw ApiError("Poné la dirección del servidor", 0)
        val api = Api(url)
        val h = api.health()
        if (!h.optBoolean("ok")) throw ApiError("Ese servidor no tiene Raphael funcionando", 0)
        val s = api.redeem(code.trim(), deviceName())
        pairCode = ""
        startSession(url, h.optString("edition"), s)
    }

    /** Un enlace `raphael://pair?host=…&code=…` (el QR escaneado con la cámara). Solo carga los datos: emparejar lo confirma la persona. */
    fun onPairLink(raw: String?) {
        val l = PairLink.parse(raw) ?: return
        if (l.host.isNotBlank()) pairHost = l.host
        pairCode = l.code
    }

    private fun deviceName() = "${Build.MANUFACTURER} ${Build.MODEL}".take(80)

    private suspend fun startSession(url: String, edition: String, s: Session) {
        prefs.server = url
        prefs.token = s.token
        prefs.user = s.user
        prefs.business = s.business
        prefs.edition = edition.ifBlank { "empresas" }
        this.edition = prefs.edition
        tab = Tab.HOY
        chat.clear()
        loggedIn = true
        PendingWorker.schedule(getApplication())
        refreshAll()
    }

    // --- Raphael personal
    fun loadPanel() = run { panel = prefs.api().panel() }
    fun loadBrain(refresh: Boolean = true) = run {
        val api = prefs.api()
        brain = api.brain(refresh)
        panel = api.panel()
    }
    fun loadConfig() = run { config = prefs.api().config() }

    /** Pone o saca claves. Nunca se guarda ni se muestra un valor completo después: el servidor devuelve solo los últimos 4. */
    fun saveConfig(set: Map<String, String>, clear: List<String> = emptyList()) = run {
        config = prefs.api().saveConfig(set, clear)
        message = if (clear.isNotEmpty()) "Quitado" else "Guardado. Ya está aplicado."
    }

    fun logout() = run {
        try {
            prefs.api().logout()
        } catch (e: ApiError) {
            // aunque el servidor no conteste, la sesión se borra del celular
        }
        PendingWorker.cancel(getApplication())
        prefs.clearSession()
        loggedIn = false
        chat.clear()
    }

    // --- datos
    fun refreshAll() = run {
        val api = prefs.api()
        summary = api.summary()
        if (personal) panel = api.panel()
        pending.replace(api.pending())
        prefs.lastNotified = maxOf(prefs.lastNotified, pending.maxOfOrNull { it.id } ?: 0)
        if (chat.isEmpty()) greet()
    }

    /** El saludo inicial tarda lo que tarde el modelo: corre aparte, sin trabar la barra de carga ni el botón Enviar. */
    private fun greet() {
        val api = prefs.api()
        viewModelScope.launch {
            try {
                if (chat.isEmpty()) askNow(api, if (personal) "buen día, ¿qué tengo para decidir hoy?" else "buen día, ¿qué tareas tenemos hoy?",
                    showOwner = false)
            } catch (e: ApiError) {
                if (e.unauthorized) onApiError(e) // si solo tardó o falló, no molesta: la persona ya puede escribir
            }
        }
    }

    fun loadPending() = run {
        pending.replace(prefs.api().pending())
        summary = prefs.api().summary()
    }

    fun loadOrders() = run { orders.replace(prefs.api().orders(showAllOrders)) }
    fun loadAgenda() = run { appointments.replace(prefs.api().appointments()) }

    /** Con la app abierta, cada 30 s: pendientes y avisos nuevos, sin barra de carga ni mensajes de error. */
    fun quietRefresh() {
        if (!loggedIn || busy) return
        viewModelScope.launch {
            try {
                val api = prefs.api()
                val u = api.updates()
                unseenNotices = u.noticesUnseen
                if (personal) panel = api.panel()
                if (u.pending != pending.size || (u.latest != (pending.maxOfOrNull { it.id } ?: 0))) pending.replace(api.pending())
                prefs.lastNotified = maxOf(prefs.lastNotified, u.latest)
            } catch (e: ApiError) {
                if (e.unauthorized) {
                    prefs.clearSession()
                    loggedIn = false
                }
            }
        }
    }

    fun loadMore() = run {
        val api = prefs.api()
        notices.replace(api.notices())
        channels = api.channels()
        if (notices.any { !it.seen }) {
            api.markNoticesSeen()
            prefs.lastNotice = maxOf(prefs.lastNotice, notices.maxOfOrNull { it.id } ?: 0)
        }
        unseenNotices = 0
        val (w, n) = api.deposits()
        depositsWaiting.replace(w)
        depositsNotified.replace(n)
        questions.replace(api.questions())
        val (st, ps) = api.catalog()
        catalogState = st
        products.replace(ps)
    }

    fun openConversation(contact: String) = run { conversation = contact to prefs.api().conversation(contact) }

    // --- decisiones (todas pasan por el servidor y su Policy Engine)
    fun approve(p: Pending, changes: Map<String, Any> = emptyMap()) = run {
        val text = prefs.api().approve(p.id, changes)
        message = if (text != null) "Listo. Se le mandó: ${text.take(160)}" else "Aprobado"
        pending.replace(prefs.api().pending())
    }

    fun reject(p: Pending, reason: String) = run {
        prefs.api().reject(p.id, reason)
        message = "Rechazado"
        pending.replace(prefs.api().pending())
    }

    fun resolve(p: Pending, reply: String) = run {
        prefs.api().resolve(p.id, reply)
        message = if (reply.isBlank()) "Marcado como resuelto" else "Respuesta enviada"
        pending.replace(prefs.api().pending())
    }

    fun setStatus(o: Order, status: String) = run {
        prefs.api().setOrderStatus(o.number, status)
        message = "Encargo #${o.number}: ${Order.STATUS_NAMES[status] ?: status}"
        orders.replace(prefs.api().orders(showAllOrders))
    }

    // --- Secretaria
    fun ask(text: String) {
        viewModelScope.launch {
            chatting = true
            try {
                askNow(prefs.api(), text, showOwner = true)
            } catch (e: ApiError) {
                onApiError(e)
            } finally {
                chatting = false
            }
        }
    }

    private suspend fun askNow(api: Api, text: String, showOwner: Boolean) {
        if (showOwner) chat.add(ChatEntry(true, text))
        val r = if (personal) api.chat(text) else api.secretary(text)
        chat.add(ChatEntry(false, r.text, r.tasks, r.options, r.suggestions))
        if (r.text.contains("Aprobada") || r.text.contains("Rechazada") || r.text.contains("resuelta") || r.text.contains("Hecho")) {
            pending.replace(api.pending())
        }
    }

    private fun <T> MutableList<T>.replace(items: List<T>) {
        clear()
        addAll(items)
    }
}
