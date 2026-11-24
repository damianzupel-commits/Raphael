package com.raphael.empresas.app

import org.json.JSONArray
import org.json.JSONObject
import java.text.NumberFormat
import java.util.Locale

private fun JSONObject.str(key: String): String = if (isNull(key)) "" else optString(key, "")
private fun JSONObject.intOrNull(key: String): Int? = if (has(key) && !isNull(key)) optInt(key) else null
private fun JSONObject.doubleOrNull(key: String): Double? = if (has(key) && !isNull(key)) optDouble(key).takeIf { !it.isNaN() } else null
private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).map { optString(it) }

/** "$ 150.000" como en el resto de Raphael. */
fun money(v: Double?): String {
    if (v == null) return "sin precio"
    val f = NumberFormat.getIntegerInstance(Locale.forLanguageTag("es-AR"))
    return "$ " + f.format(Math.round(v))
}

/** "2026-11-19" -> "19/11". */
fun shortDate(iso: String?): String {
    if (iso.isNullOrBlank() || iso.length < 10) return "sin fecha"
    return iso.substring(8, 10) + "/" + iso.substring(5, 7)
}

data class Session(val token: String, val user: String, val business: String)

data class Summary(val user: String, val business: String, val pending: Int, val pendingHuman: Int, val notices: Int,
                   val healthOk: Boolean?) {
    companion object {
        fun from(o: JSONObject) = Summary(o.str("user"), o.str("business"), o.optInt("pending"), o.optInt("pending_human"),
            o.optInt("notices"), o.optJSONObject("health")?.optBoolean("ok"))
    }
}

data class Updates(val pending: Int, val pendingHuman: Int, val latest: Int, val items: List<String>,
                   val noticesUnseen: Int = 0, val noticeLatest: Int = 0, val noticeLast: String = "") {
    companion object {
        fun from(o: JSONObject): Updates {
            val a = o.optJSONArray("items")
            val items = if (a == null) emptyList() else (0 until a.length()).mapNotNull { a.optJSONObject(it)?.str("summary") }
            return Updates(o.optInt("pending"), o.optInt("pending_human"), o.optInt("latest"), items,
                o.optInt("notices_unseen"), o.optInt("notice_latest"), o.str("notice_last"))
        }
    }
}

/** Un aviso del servidor: mensajes que no se pudieron mandar, brigada con problemas, recordatorios. */
data class Notice(val id: Int, val text: String, val time: String, val kind: String, val seen: Boolean) {
    val failedSend get() = kind == "envio_fallido"

    companion object {
        fun from(o: JSONObject) = Notice(o.optInt("id"), o.str("text"), o.str("when"), o.str("kind"), o.optBoolean("seen"))
    }
}

/** Cómo están WhatsApp e Instagram en el servidor. */
data class Channels(val mode: String, val channels: List<String>, val problems: List<String>) {
    val real get() = mode == "real"

    companion object {
        fun from(o: JSONObject) = Channels(o.str("mode"), o.optJSONArray("channels").strings(), o.optJSONArray("problems").strings())
    }
}

data class Pending(val id: Int, val type: String, val level: String, val summary: String, val contact: String?,
                   val created: String, val data: JSONObject, val editable: List<String>, val can: List<String>) {
    val human get() = level == "humano"
    val title: String get() = TYPE_TITLES[type] ?: "Para decidir"

    companion object {
        val TYPE_TITLES = mapOf(
            "enviar_presupuesto" to "Presupuesto", "confirmar_pago" to "Seña", "confirmar_turno" to "Turno",
            "responder_duda" to "Pregunta de un cliente", "derivar_humano" to "Reclamo", "cancelar_pedido" to "Cancelación",
            "trust" to "Confianza", "aviso_tope" to "Tope del plan")

        fun from(o: JSONObject) = Pending(o.optInt("id"), o.str("type"), o.str("level"), o.str("summary"),
            o.str("contact").ifBlank { null }, o.str("created"), o.optJSONObject("data") ?: JSONObject(),
            o.optJSONArray("editable").strings(), o.optJSONArray("can").strings())
    }
}

data class TaskItem(val id: Int, val kind: String, val title: String, val reason: String, val pending: Int?)

data class OptionItem(val title: String, val detail: String, val recommended: Boolean)

data class SecretaryReply(val text: String, val suggestions: List<String>, val tasks: List<TaskItem>,
                          val options: List<OptionItem>, val cardPending: Int?) {
    companion object {
        fun from(o: JSONObject): SecretaryReply {
            val ta = o.optJSONArray("tasks")
            val tasks = if (ta == null) emptyList() else (0 until ta.length()).mapNotNull { i ->
                ta.optJSONObject(i)?.let { TaskItem(it.optInt("id"), it.str("kind"), it.str("title"), it.str("reason"), it.intOrNull("pending")) }
            }
            val card = o.optJSONObject("card")
            val oa = card?.optJSONArray("options")
            val opts = if (oa == null) emptyList() else (0 until oa.length()).mapNotNull { i ->
                oa.optJSONObject(i)?.let { OptionItem(it.str("title"), it.str("detail"), it.optBoolean("recommended")) }
            }
            return SecretaryReply(o.str("text"), o.optJSONArray("suggestions").strings(), tasks, opts,
                card?.optJSONObject("pending")?.optInt("id"))
        }
    }
}

data class Order(val number: Int, val client: String, val description: String, val due: String?, val status: String,
                 val price: Double?, val deposit: Double?, val paid: Double, val urgent: Boolean, val contact: String?,
                 val measures: String, val notes: String) {
    companion object {
        val STATUS_NAMES = linkedMapOf("presupuesto" to "Presupuesto", "confirmado" to "Confirmado",
            "en_confeccion" to "En confección", "prueba" to "Para probar", "listo" to "Listo", "entregado" to "Entregado",
            "cancelado" to "Cancelado")
        /** Los estados que la dueña puede poner a mano (los otros los pone el circuito: presupuesto y seña). */
        val SETTABLE = listOf("en_confeccion", "prueba", "listo", "entregado", "cancelado")

        fun from(o: JSONObject) = Order(o.optInt("number"), o.str("client"), o.str("description"), o.str("due").ifBlank { null },
            o.str("status"), o.doubleOrNull("price"), o.doubleOrNull("deposit"), o.optDouble("paid", 0.0),
            o.optBoolean("urgent"), o.str("contact").ifBlank { null }, o.str("measures"), o.str("notes"))
    }
}

data class Appointment(val date: String, val time: String, val reason: String, val name: String, val contact: String?) {
    companion object {
        fun from(o: JSONObject) = Appointment(o.str("date"), o.str("time"), o.str("reason"), o.str("name"), o.str("contact").ifBlank { null })
    }
}

data class Deposit(val number: Int, val client: String, val deposit: Double?, val status: String, val since: String) {
    companion object {
        fun from(o: JSONObject) = Deposit(o.optInt("number"), o.str("client"), o.doubleOrNull("deposit"), o.str("status"), o.str("since"))
    }
}

data class Question(val number: Int, val contact: String, val question: String, val status: String, val reply: String) {
    companion object {
        fun from(o: JSONObject) = Question(o.optInt("number"), o.str("contact"), o.str("question"), o.str("status"), o.str("reply"))
    }
}

data class Product(val id: String, val title: String, val price: Double?, val stock: Int?, val url: String) {
    companion object {
        fun from(o: JSONObject) = Product(o.str("id"), o.str("title"), o.doubleOrNull("price"), o.intOrNull("stock"), o.str("url"))
    }
}

data class CatalogState(val configured: Boolean, val count: Int, val lastOk: String, val error: String) {
    companion object {
        fun from(o: JSONObject) = CatalogState(o.optBoolean("configured"), o.optInt("count"), o.str("last_ok"), o.str("error"))
    }
}

data class ChatLine(val fromClient: Boolean, val text: String, val time: String) {
    companion object {
        fun from(o: JSONObject) = ChatLine(o.str("from") == "contact", o.str("text"), o.str("when"))
    }
}
