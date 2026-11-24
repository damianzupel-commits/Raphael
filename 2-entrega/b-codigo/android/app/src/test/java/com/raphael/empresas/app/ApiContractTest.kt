package com.raphael.empresas.app

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * El cliente de la app contra la API de verdad (raphael-empresas-api/scripts/servidor_de_prueba.py).
 * Solo corre si está RAPHAEL_API_URL (ej. http://127.0.0.1:8799); si no, se saltea.
 */
class ApiContractTest {
    private val base = System.getenv("RAPHAEL_API_URL")

    @Test fun recorrido_de_la_duena() = runBlocking {
        assumeTrue("sin RAPHAEL_API_URL", !base.isNullOrBlank())
        val anon = Api(base!!)
        assertTrue(anon.health().getBoolean("ok"))
        try {
            anon.login("mala", "test"); fail("entró con clave mala")
        } catch (e: ApiError) {
            assertEquals(401, e.code)
        }
        val s = anon.login("clave-de-prueba", "test")
        assertEquals("Ana", s.user)
        val api = Api(base, s.token)

        val pend = api.pending()
        val quote = pend.first { it.type == "enviar_presupuesto" }
        val claim = pend.first { it.type == "derivar_humano" }
        assertEquals(listOf("price"), quote.editable)
        assertTrue(claim.human && claim.can == listOf("resolve"))
        assertTrue(api.updates().pending >= 2)

        val r = api.secretary("buen día, ¿qué tareas hay?")
        assertTrue(r.text.contains("Buen día, Ana"))
        assertEquals("derivar_humano", r.tasks.first().kind)
        val card = api.secretary("contame la 1")
        assertTrue(card.options.first().recommended)

        val text = api.approve(quote.id, mapOf("price" to 210000.0))
        assertTrue(text!!.contains("$ 210.000"))
        api.resolve(claim.id, "Hola Marta, ¿me mandás una foto?")
        assertTrue(api.pending().isEmpty())

        val o = api.orders().first()
        assertEquals("presupuesto", o.status)
        try {
            api.setOrderStatus(o.number, "borrado"); fail("aceptó un estado inventado")
        } catch (e: ApiError) {
            assertEquals(422, e.code)
        }
        assertEquals("listo", api.setOrderStatus(o.number, "listo").status)
        assertTrue(api.conversation("whatsapp:9").any { it.text.contains("me mandás una foto") })
        assertTrue(api.appointments().isEmpty())
        assertTrue(!api.catalog().first.configured)
        assertEquals(null, api.channels().mode.takeIf { it.isNotBlank() })   // el servidor de prueba no tiene canal de Meta
        api.notices()
        api.markNoticesSeen()
        assertEquals(0, api.updates().noticesUnseen)
        api.logout()
        try {
            api.summary(); fail("la sesión siguió viva")
        } catch (e: ApiError) {
            assertTrue(e.unauthorized)
        }
    }
}
