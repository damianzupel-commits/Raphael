package com.raphael.empresas.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** Un error de la API con el mensaje del servidor (ya en castellano) y el código HTTP. 0 = sin conexión. */
class ApiError(message: String, val code: Int) : Exception(message) {
    val unauthorized get() = code == 401
}

/**
 * Cliente de la API de Raphael Empresas (contrato en codigo/api/API.md, versión 1).
 * Sin librerías externas: HttpURLConnection + org.json. Todo corre en Dispatchers.IO.
 */
class Api(private val baseUrl: String, private val token: String? = null) {

    private fun url(path: String) = URL(baseUrl.trimEnd('/') + path)

    private suspend fun call(method: String, path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
        val conn = try {
            url(path).openConnection() as HttpURLConnection
        } catch (e: Exception) {
            throw ApiError("La dirección del servidor no es válida", 0)
        }
        try {
            conn.requestMethod = method
            conn.connectTimeout = 10_000
            conn.readTimeout = 60_000
            conn.setRequestProperty("Accept", "application/json")
            token?.let { conn.setRequestProperty("Authorization", "Bearer $it") }
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            if (code !in 200..299) throw ApiError(detail(text) ?: "El servidor respondió $code", code)
            if (text.isBlank()) JSONObject() else JSONObject(text)
        } catch (e: ApiError) {
            throw e
        } catch (e: IOException) {
            throw ApiError("No me puedo conectar con el servidor. Revisá la conexión.", 0)
        } catch (e: Exception) {
            throw ApiError("Respuesta inesperada del servidor", 0)
        } finally {
            conn.disconnect()
        }
    }

    private fun detail(text: String): String? = try {
        val d = JSONObject(text).opt("detail")
        when (d) {
            is String -> d
            is JSONArray -> d.optJSONObject(0)?.optString("msg")
            else -> null
        }
    } catch (e: Exception) {
        null
    }

    // --- sin sesión
    suspend fun health(): JSONObject = call("GET", "/api/v1/health")

    suspend fun login(key: String, device: String): Session {
        val r = call("POST", "/api/v1/login", JSONObject().put("key", key).put("device", device))
        return Session(r.getString("token"), r.optString("user"), r.optString("business"))
    }

    /** Emparejar con el código del QR (sin clave): el servidor lo da por un solo uso y por 5 minutos. */
    suspend fun redeem(code: String, device: String): Session {
        val r = call("POST", "/api/v1/phone/redeem", JSONObject().put("code", code).put("device", device))
        return Session(r.getString("token"), r.optString("user"), "")
    }

    // --- con sesión
    suspend fun logout() { call("POST", "/api/v1/logout") }
    suspend fun summary(): Summary = Summary.from(call("GET", "/api/v1/summary"))
    suspend fun updates(): Updates = Updates.from(call("GET", "/api/v1/updates"))
    suspend fun pending(): List<Pending> = list(call("GET", "/api/v1/pending"), "items", Pending::from)

    suspend fun approve(id: Int, changes: Map<String, Any> = emptyMap()): String? {
        val r = call("POST", "/api/v1/pending/$id/approve", JSONObject().put("changes", JSONObject(changes)))
        return r.optString("text").takeIf { it.isNotBlank() && it != "null" }
    }

    suspend fun reject(id: Int, reason: String) {
        call("POST", "/api/v1/pending/$id/reject", JSONObject().put("reason", reason))
    }

    suspend fun resolve(id: Int, reply: String) {
        call("POST", "/api/v1/pending/$id/resolve", JSONObject().put("reply", reply))
    }

    suspend fun secretary(text: String, session: String = "app"): SecretaryReply =
        SecretaryReply.from(call("POST", "/api/v1/secretary", JSONObject().put("text", text).put("session", session)))

    /** Raphael personal: hablarle al orquestador maestro (misma forma de respuesta que la Secretaria). */
    suspend fun chat(text: String, session: String = "app"): SecretaryReply =
        SecretaryReply.from(call("POST", "/api/v1/chat", JSONObject().put("text", text).put("session", session)))

    suspend fun brain(refresh: Boolean = false): Brain = Brain.from(call("GET", "/api/v1/brain?refresh=$refresh"))
    suspend fun config(): ConfigView = ConfigView.from(call("GET", "/api/v1/config"))

    suspend fun saveConfig(set: Map<String, String>, clear: List<String> = emptyList()): ConfigView =
        ConfigView.from(call("PUT", "/api/v1/config", JSONObject().put("set", JSONObject(set)).put("clear", JSONArray(clear))))

    suspend fun orders(all: Boolean = false): List<Order> = list(call("GET", "/api/v1/orders?all=$all"), "items", Order::from)
    suspend fun setOrderStatus(number: Int, status: String): Order =
        Order.from(call("POST", "/api/v1/orders/$number/status", JSONObject().put("status", status)))

    suspend fun appointments(): List<Appointment> = list(call("GET", "/api/v1/appointments"), "items", Appointment::from)

    suspend fun deposits(): Pair<List<Deposit>, List<Deposit>> {
        val r = call("GET", "/api/v1/deposits")
        return list(r, "waiting", Deposit::from) to list(r, "notified", Deposit::from)
    }

    suspend fun questions(): List<Question> = list(call("GET", "/api/v1/questions"), "items", Question::from)

    suspend fun catalog(q: String = ""): Pair<CatalogState, List<Product>> {
        val r = call("GET", "/api/v1/catalog" + if (q.isBlank()) "" else "?q=" + URLEncoder.encode(q, "UTF-8"))
        return CatalogState.from(r.optJSONObject("state") ?: JSONObject()) to list(r, "items", Product::from)
    }

    suspend fun notices(): List<Notice> = list(call("GET", "/api/v1/notices"), "items", Notice::from)
    suspend fun markNoticesSeen() { call("POST", "/api/v1/notices/seen") }
    suspend fun channels(): Channels = Channels.from(call("GET", "/api/v1/channels"))

    suspend fun conversation(contact: String): List<ChatLine> =
        list(call("GET", "/api/v1/conversation/" + URLEncoder.encode(contact, "UTF-8")), "items", ChatLine::from)

    private fun <T> list(o: JSONObject, key: String, f: (JSONObject) -> T): List<T> {
        val a = o.optJSONArray(key) ?: return emptyList()
        return (0 until a.length()).mapNotNull { a.optJSONObject(it)?.let(f) }
    }
}
