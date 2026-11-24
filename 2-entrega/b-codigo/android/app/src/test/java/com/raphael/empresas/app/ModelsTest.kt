package com.raphael.empresas.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelsTest {
    @Test fun money_como_en_raphael() {
        assertTrue(money(150000.0).startsWith("$ 150"))
        assertEquals("sin precio", money(null))
    }

    @Test fun fecha_corta() {
        assertEquals("19/11", shortDate("2026-11-19"))
        assertEquals("sin fecha", shortDate(null))
    }

    @Test fun servidor_sin_esquema_va_por_https() {
        assertEquals("https://negocio.duckdns.org", normalizeServer(" negocio.duckdns.org/ "))
        assertEquals("http://192.168.1.50:8787", normalizeServer("http://192.168.1.50:8787"))
    }

    @Test fun pendiente_desde_la_api() {
        val p = Pending.from(JSONObject("""{"id":7,"type":"enviar_presupuesto","level":"aprobacion","summary":"Encargo #1",
            "contact":"whatsapp:1","created":"2026-11-18T10:00:00","data":{"number":1,"price":150000},
            "editable":["price"],"can":["approve","reject"]}"""))
        assertEquals(7, p.id)
        assertEquals("Presupuesto", p.title)
        assertEquals(listOf("price"), p.editable)
        assertEquals(false, p.human)
    }

    @Test fun encargo_sin_precio() {
        val o = Order.from(JSONObject("""{"number":3,"client":"Lu","description":"vestido","due":null,"status":"presupuesto",
            "price":null,"deposit":null,"paid":0,"urgent":true,"contact":"whatsapp:1","measures":"","notes":""}"""))
        assertNull(o.price)
        assertNull(o.due)
        assertTrue(o.urgent)
    }

    @Test fun respuesta_de_la_secretaria() {
        val r = SecretaryReply.from(JSONObject("""{"text":"Tenemos 1 cosa","suggestions":["Contame la 1"],
            "tasks":[{"id":1,"kind":"derivar_humano","title":"Reclamo de Marta","reason":"pidió hablar","pending":4}],
            "card":null,"meta":{}}"""))
        assertEquals(1, r.tasks.size)
        assertEquals(4, r.tasks[0].pending)
        assertTrue(r.options.isEmpty())
    }

    @Test fun avisos_y_canales() {
        val u = Updates.from(JSONObject("""{"pending":0,"pending_human":0,"latest":0,"items":[],"notices_unseen":2,
            "notice_latest":9,"notice_last":"No le pude mandar el mensaje"}"""))
        assertEquals(2, u.noticesUnseen)
        assertEquals(9, u.noticeLatest)
        val n = Notice.from(JSONObject("""{"id":9,"text":"x","when":"2026-11-23T10:00:00","kind":"envio_fallido","seen":false}"""))
        assertTrue(n.failedSend)
        val c = Channels.from(JSONObject("""{"mode":"mock","channels":["instagram","whatsapp"],"problems":[]}"""))
        assertEquals(false, c.real)
        assertEquals(2, c.channels.size)
    }
}
