package com.raphael.empresas.app

import android.content.Context
import androidx.core.content.edit

/**
 * Lo que la app guarda: la dirección del servidor y la sesión (el token, nunca la clave).
 * Vive en el almacenamiento privado de la app y está excluido de los respaldos (data_extraction_rules).
 */
class Prefs(context: Context) {
    private val p = context.getSharedPreferences("raphael", Context.MODE_PRIVATE)

    var server: String
        get() = p.getString("server", null) ?: BuildConfig.DEFAULT_SERVER
        set(v) = p.edit { putString("server", v.trim().trimEnd('/')) }
    var token: String?
        get() = p.getString("token", null)
        set(v) = p.edit { putString("token", v) }
    var user: String
        get() = p.getString("user", "") ?: ""
        set(v) = p.edit { putString("user", v) }
    var business: String
        get() = p.getString("business", "") ?: ""
        set(v) = p.edit { putString("business", v) }
    /** El número de pendiente más alto que ya se avisó (para no repetir notificaciones). */
    var lastNotified: Int
        get() = p.getInt("last_notified", 0)
        set(v) = p.edit { putInt("last_notified", v) }

    /** El último aviso del servidor que ya se mostró en una notificación. */
    var lastNotice: Int
        get() = p.getInt("last_notice", 0)
        set(v) = p.edit { putInt("last_notice", v) }

    val loggedIn get() = !token.isNullOrBlank() && server.isNotBlank()

    fun api() = Api(server, token)

    fun clearSession() {
        p.edit { remove("token"); remove("last_notified"); remove("last_notice") }
    }
}

/** http:// solo para la red local en debug; en release el sistema lo bloquea igual (network_security_config). */
fun normalizeServer(raw: String): String {
    val s = raw.trim().trimEnd('/')
    if (s.isEmpty()) return s
    return if (s.startsWith("http://") || s.startsWith("https://")) s else "https://$s"
}
