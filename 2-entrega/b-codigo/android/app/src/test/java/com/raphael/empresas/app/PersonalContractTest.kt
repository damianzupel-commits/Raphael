package com.raphael.empresas.app

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * El cliente de la app contra el servidor de Raphael personal de verdad.
 * Solo corre con RAPHAEL_PERSONAL_URL (ej. http://127.0.0.1:8788) y RAPHAEL_PERSONAL_KEY (la clave de la app); si no, se saltea.
 *   python -m raphael_personal_api servir --instalacion ... --datos ... --port 8788
 */
class PersonalContractTest {
    private val base = System.getenv("RAPHAEL_PERSONAL_URL")
    private val key = System.getenv("RAPHAEL_PERSONAL_KEY")

    @Test fun recorrido_de_raphael_personal() = runBlocking {
        assumeTrue("sin RAPHAEL_PERSONAL_URL o RAPHAEL_PERSONAL_KEY", !base.isNullOrBlank() && !key.isNullOrBlank())
        val anon = Api(base!!)
        val h = anon.health()
        assertTrue(h.getBoolean("ok"))
        assertEquals("personal", h.getString("edition"))
        try {
            anon.login("clave-mala-xx", "test"); fail("entró con clave mala")
        } catch (e: ApiError) {
            assertEquals(401, e.code)
        }
        try {
            anon.redeem("ZZZZZZZZ", "test"); fail("canjeó un código inventado")
        } catch (e: ApiError) {
            assertEquals(401, e.code)
        }
        val api = Api(base, anon.login(key!!, "test").token)

        assertTrue(api.chat("hola").text.isNotBlank())
        assertTrue(api.pending().all { it.can.isNotEmpty() })          // nada se aprueba solo: cada uno espera a la persona
        val b = api.brain(refresh = true)
        assertTrue(b.privateBrigades.containsAll(listOf("seguridad", "investigacion", "memoria", "operaciones")))
        if (!b.localReady) assertEquals("reglas", b.privateMode)        // sin modelo local, lo privado no va a la nube

        val c = api.config()
        assertTrue(c.fields.any { it.name == "NVIDIA_API_KEY" })
        assertTrue(c.fields.filter { it.secret }.all { it.value.isEmpty() })   // un secreto nunca vuelve entero
        assertFalse(api.saveConfig(mapOf("RAPHAEL_ROL_MANDO" to "local")).fields.isEmpty())
        api.saveConfig(emptyMap(), listOf("RAPHAEL_ROL_MANDO"))
        try {
            api.saveConfig(mapOf("RAPHAEL_ROL_VOZ" to "nube")); fail("aceptó un escalón inexistente")
        } catch (e: ApiError) {
            assertEquals(400, e.code)
        }
        api.logout()
        try {
            api.summary(); fail("la sesión siguió viva")
        } catch (e: ApiError) {
            assertTrue(e.unauthorized)
        }
    }
}
