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

    // --- Raphael personal
    @Test fun enlace_del_qr_de_emparejamiento() {
        val l = PairLink.parse("raphael://pair?host=https://pc.tail1.ts.net&code=abcd2345")!!
        assertEquals("https://pc.tail1.ts.net", l.host)
        assertEquals("ABCD2345", l.code)
        assertEquals("", PairLink.parse("raphael://pair?code=ZZZZ9999")!!.host)
    }

    @Test fun enlaces_que_no_son_de_emparejamiento_se_ignoran() {
        assertNull(PairLink.parse(null))
        assertNull(PairLink.parse("https://pair?code=ABCD2345"))
        assertNull(PairLink.parse("raphael://pair?host=https://x"))
        assertNull(PairLink.parse("raphael://pair?code=<script>"))
    }

    @Test fun configuracion_no_trae_secretos_completos() {
        val v = ConfigView.from(JSONObject("""{"fields":[
            {"name":"NVIDIA_API_KEY","group":"ia","label":"Clave de NVIDIA","secret":true,"help":"","set":true,"hint":"…9876","live":true},
            {"name":"OLLAMA_MODEL","group":"local","label":"Ollama: modelo","secret":false,"set":true,"value":"llama3.1:8b","live":true}],
            "checks":[{"area":"IA local","status":"aviso","text":"no hay modelo local prendido"}],"restart_needed":["MP_MODE"]}"""))
        assertEquals(2, v.fields.size)
        assertTrue(v.fields[0].secret && v.fields[0].hint == "…9876" && v.fields[0].value.isEmpty())
        assertEquals("llama3.1:8b", v.fields[1].value)
        assertEquals("aviso", v.checks[0].status)
        assertEquals(listOf("MP_MODE"), v.restartNeeded)
    }

    @Test fun cerebro_dice_si_el_local_esta_prendido() {
        val b = Brain.from(JSONObject("""{"local":{"ready":false,"hints":["ollama no responde"]},
            "private":["seguridad","memoria"],"private_mode":"reglas",
            "roles":{"mando":{"tiers":["gratis","local"],"now":"nvidia"},"ruteo":{"tiers":["local","gratis"],"now":""}}}"""))
        assertTrue(!b.localReady)
        assertEquals("reglas", b.privateMode)
        assertEquals(listOf("seguridad", "memoria"), b.privateBrigades)
        assertEquals(listOf("local", "gratis"), b.roles.first { it.role == "ruteo" }.tiers)
    }

    @Test fun pendiente_de_raphael_personal_sin_campos_de_empresas() {
        val p = Pending.from(JSONObject("""{"id":3,"type":"ejecutar_orden","brigade":"trading","level":"humano",
            "summary":"Comprar USD/JPY","created":"x","data":{},"can":["resolve"]}"""))
        assertTrue(p.human && p.editable.isEmpty() && p.contact == null)
    }

    private val panelJson = """{"contract":"2.1.0","edition":"personal","down":1,
        "brigades":[{"id":"seguridad","name":"Seguridad","mounted":true,"active":true,"private":true,
                     "cooks":[{"id":"vigia","state":"en espera"},{"id":"salud","state":"caída"}]},
                    {"id":"trading","name":"Trading","mounted":true,"active":true,"private":false,"cooks":[{"id":"mesa","state":"en espera"}]},
                    {"id":"legales","name":"Legales","mounted":false,"active":true,"private":false,"cooks":[]}],
        "tasks":[{"title":"revisar puertos","brigade":"Seguridad","state":"en curso","who":"vigia","pending":null},
                 {"title":"Comprar USD/JPY","brigade":"Trading","state":"te toca a vos","who":"mesa","pending":7}],
        "ephemerals":[{"helper":"h1","brigade":"Seguridad","task":"nmap","time":"3s"}],
        "tools":[{"name":"web","owner":"uso compartido","level":"automatico","enabled":true},
                 {"name":"orden","owner":"Trading","level":"humano","enabled":false}]}"""

    @Test fun panel_como_el_de_la_pc() {
        val p = PanelData.from(JSONObject(panelJson))
        assertEquals(2, p.mounted.size)
        assertEquals(1, p.running)
        assertEquals(1, p.toApprove)
        assertEquals(7, p.tasks.last().pending)
        assertTrue(p.tasks.first().pending == null)
        assertTrue(isBad(p.brigades.first().cooks.last().state))
    }

    @Test fun panel_de_una_sola_brigada() {
        val p = PanelData.from(JSONObject(panelJson)).scoped("trading")
        assertEquals(listOf("trading"), p.brigades.map { it.id })
        assertEquals(listOf("Comprar USD/JPY"), p.tasks.map { it.title })
        assertTrue(p.ephemerals.isEmpty())
        assertEquals(listOf("web", "orden"), p.tools.map { it.name })      // lo suyo y lo de uso compartido
        assertEquals(3, PanelData.from(JSONObject(panelJson)).scoped(null).brigades.size)
        assertEquals(3, PanelData.from(JSONObject(panelJson)).scoped("no-existe").brigades.size)
    }

    @Test fun cada_brigada_tiene_su_icono_y_la_desconocida_uno_neutro() {
        assertEquals("◈", Looks.of("seguridad").icon)
        assertEquals("⌖", Looks.of("04-geolocalizacion-publica").icon)
        assertEquals("●", Looks.of("algo-nuevo").icon)
        assertEquals("R A P H A E L", spaced("Raphael"))
    }
}
