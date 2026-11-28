"""Cliente web de Raphael personal (una sola página, sin dependencias): hablar, aprobar, ver el cerebro y configurar.

Sirve desde la PC y, por Tailscale, desde el celular. Todo lo que viene de las brigadas o de terceros se pone con
`textContent` (nunca como HTML). La sesión vive solo en la pestaña."""

PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raphael</title>
<style>
:root{--bg:#f6f5f2;--fg:#1d1c1a;--mut:#6b6862;--card:#fff;--bd:#dedbd4;--ac:#2f5d50;--ok:#2e7d4f;--wa:#a8660b;--er:#b3382c}
@media(prefers-color-scheme:dark){:root{--bg:#151513;--fg:#ecebe7;--mut:#a09d95;--card:#1f1f1c;--bd:#33322e;--ac:#7fb5a3;--ok:#6cc08b;--wa:#e0a24d;--er:#ef7d70}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 16px 60px}h1{font-size:1.3rem;margin:.2em 0}h2{font-size:1.05rem;margin:0 0 .6em}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin:12px 0}
label{display:block;font-weight:600;margin-top:10px}small,.mut{color:var(--mut);font-weight:400}
input,select,textarea{width:100%;padding:10px;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--fg);font:inherit}
button{padding:10px 16px;border:0;border-radius:8px;background:var(--ac);color:var(--bg);font:inherit;font-weight:600;cursor:pointer}
button.sec{background:transparent;color:var(--fg);border:1px solid var(--bd)}button.mini{padding:4px 10px;font-size:.85rem}
.row{display:flex;gap:8px;align-items:center}.row input{flex:1}.st{font-size:.9rem;margin:2px 0}
.ok{color:var(--ok)}.aviso{color:var(--wa)}.falta{color:var(--er)}.info{color:var(--mut)}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}nav button{flex:1}nav button.on{background:var(--ac);color:var(--bg)}nav button:not(.on){background:transparent;color:var(--fg);border:1px solid var(--bd)}
#msg{position:sticky;top:0;padding:10px;border-radius:8px;margin:8px 0;display:none;z-index:2}#msg.e{background:var(--er);color:#fff;display:block}#msg.g{background:var(--ok);color:#fff;display:block}
.hide{display:none}.b{padding:8px 12px;border-radius:10px;margin:6px 0;white-space:pre-wrap;max-width:92%}.me{background:var(--ac);color:var(--bg);margin-left:auto}.ra{background:var(--card);border:1px solid var(--bd)}
#log{max-height:55vh;overflow:auto}
</style></head><body><main>
<h1>Raphael <button class="sec mini" onclick="location.reload()" title="Recargar la interfaz" aria-label="Recargar la interfaz">↻</button></h1>
<div id="msg" role="status"></div>
<section id="login" class="card"><h2>Entrar</h2>
<label for="k">Clave de la app</label><input id="k" type="password" autocomplete="current-password">
<p class="mut">La primera vez, la clave está en la ventana de Raphael y en el archivo <code>clave-inicial.txt</code> de la carpeta de datos.</p>
<button id="go">Entrar</button></section>
<div id="app" class="hide">
<nav id="tabs"></nav>
<section id="t-hablar" class="card"><div id="log"></div>
<div class="row" style="margin-top:10px"><input id="say" placeholder="Decime qué necesitás" autocomplete="off"><button id="send">Enviar</button></div></section>
<section id="t-campo" class="card hide"><h2>Campo</h2>
<div class="row"><select id="cneg" aria-label="Negocio"></select><button id="cnew" class="sec mini">Nuevo</button></div>
<div id="cnewrow" class="row hide" style="margin-top:8px"><input id="cnn" placeholder="Nombre del negocio"><button id="cmk" class="mini">Crear</button></div>
<div id="ctemas" class="row" style="flex-wrap:wrap;margin-top:10px"></div>
<textarea id="ctxt" rows="3" placeholder="Qué viste (tocá un tema o dejá en Auto)" style="margin-top:8px"></textarea>
<div class="row" style="margin-top:8px;flex-wrap:wrap"><button id="csave">Guardar nota</button><button id="cmic" class="sec">🎤 Grabar</button>
<label class="sec" style="display:inline-block;margin:0;padding:10px 16px;border:1px solid var(--bd);border-radius:8px;cursor:pointer;font-weight:600">📷 Foto<input id="cfoto" type="file" accept="image/*" capture="environment" style="display:none"></label></div>
<div id="cst" class="mut" style="margin-top:6px"></div>
<h2 style="margin-top:16px">Hoy</h2><div id="choy"></div>
<h2 style="margin-top:16px">Cierre del día <small>(las 3 cosas que más tiempo o plata hicieron perder)</small></h2>
<input id="cc1" placeholder="1"><input id="cc2" placeholder="2" style="margin-top:6px"><input id="cc3" placeholder="3" style="margin-top:6px">
<div class="row" style="margin-top:8px;flex-wrap:wrap"><button id="ccl">Guardar cierre</button><button id="cres" class="sec">Resumen del día</button><button id="cresia" class="sec">Resumen con IA local</button></div>
<h2 style="margin-top:16px">Preguntarle al expediente</h2>
<div class="row"><input id="cq" placeholder="¿cuántas veces faltó stock?"><button id="cask">Preguntar</button></div>
<div class="row" style="margin-top:8px"><button id="cexp" class="sec">Ver expediente</button><button id="cdl" class="sec">Bajar .md</button></div>
<pre id="cout" class="mut" style="white-space:pre-wrap;margin-top:10px"></pre></section>
<section id="t-pend" class="card hide"><h2>Pendientes de tu aprobación</h2><div id="pend"></div></section>
<section id="t-cerebro" class="card hide"><h2>Cerebro</h2><div id="brain"></div></section>
<div id="t-config" class="hide"><section class="card"><h2>Estado</h2><div id="checks"></div></section><div id="groups"></div>
<section class="card"><h2>Emparejar el celular</h2><p class="mut">Genera un código de un solo uso (5 minutos). Escaneá el QR con la cámara del celular: se abre la app de Raphael con el código cargado.</p>
<button id="pairb" class="sec">Generar código</button><div id="pair" style="margin-top:10px"></div></section>
<section class="card"><h2>Clave de la app</h2><label for="nk">Clave nueva <small>(mínimo 8 caracteres)</small></label>
<input id="nk" type="password" autocomplete="new-password"><p class="mut">Al cambiarla se cierran las demás sesiones.</p>
<button id="chk" class="sec">Cambiar clave</button></section></div>
<p><button id="out" class="sec">Salir</button></p></div>
<script>
const TABS=[["hablar","Hablar"],["campo","Campo"],["pend","Pendientes"],["cerebro","Cerebro"],["config","Configuración"]];
const G={ia:"Inteligencia artificial (nube)",local:"Modelo local (Ollama / LM Studio)",roles:"Qué modelo usa cada rol",red:"Celular",voz:"Voz",cuentas:"Otras cuentas"};
const $=id=>document.getElementById(id);let tok=null;try{tok=sessionStorage.getItem("t")}catch(e){}
function say(t,ok){const m=$("msg");m.textContent=t;m.className=ok?"g":"e";clearTimeout(say.t);say.t=setTimeout(()=>m.className="",6000)}
async function api(p,o={}){const h={"Content-Type":"application/json"};if(tok)h.Authorization="Bearer "+tok;
 const r=await fetch(p,{...o,headers:h});let d={};try{d=await r.json()}catch(e){}
 if(r.status===401&&tok){tok=null;try{sessionStorage.removeItem("t")}catch(e){}show(false)}
 if(!r.ok)throw new Error(d.detail||("Error "+r.status));return d}
function show(on){$("login").classList.toggle("hide",on);$("app").classList.toggle("hide",!on)}
function el(t,a,...k){const e=document.createElement(t);Object.assign(e,a||{});k.forEach(x=>e.append(x));return e}
function tab(n){TABS.forEach(([k])=>{const s=$(k==="config"?"t-config":"t-"+k);s.classList.toggle("hide",k!==n)});
 [...$("tabs").children].forEach((b,i)=>b.classList.toggle("on",TABS[i][0]===n));
 if(n==="campo")loadCampo();if(n==="pend")loadPend();if(n==="cerebro")loadBrain();if(n==="config")loadCfg()}
TABS.forEach(([k,t])=>{const b=el("button",{textContent:t});b.onclick=()=>tab(k);$("tabs").append(b)});
function bub(t,me){const b=el("div",{className:"b "+(me?"me":"ra")});b.textContent=t;$("log").append(b);$("log").scrollTop=1e9}
async function send(){const t=$("say").value.trim();if(!t)return;$("say").value="";bub(t,true);
 try{const d=await api("/api/v1/chat",{method:"POST",body:JSON.stringify({text:t})});bub(d.text||d.message||"(sin respuesta)",false)}catch(e){say(e.message)}}
$("send").onclick=send;$("say").onkeydown=e=>{if(e.key==="Enter")send()};
async function loadPend(){try{const d=await api("/api/v1/pending");const p=$("pend");p.replaceChildren();
 if(!d.items.length)p.append(el("p",{className:"mut",textContent:"No hay nada esperando."}));
 for(const i of d.items){const c=el("div",{className:"card"});c.append(el("div",{textContent:"#"+i.id+" · "+i.summary}),el("div",{className:"mut",textContent:(i.brigade||"")+" · "+i.level}));
  const r=el("div",{className:"row",style:"margin-top:8px"});
  if(i.can.includes("approve")){const a=el("button",{textContent:"Aprobar"});a.onclick=()=>act(i.id,"approve",{});r.append(a);
   const x=el("button",{className:"sec",textContent:"Rechazar"});x.onclick=()=>act(i.id,"reject",{reason:""});r.append(x)}
  if(i.can.includes("resolve")){const t=el("input",{placeholder:"Tu respuesta"});const b=el("button",{textContent:"Resolver"});b.onclick=()=>act(i.id,"resolve",{reply:t.value});r.append(t,b)}
  c.append(r);p.append(c)}}catch(e){say(e.message)}}
async function act(id,what,body){try{await api("/api/v1/pending/"+id+"/"+what,{method:"POST",body:JSON.stringify(body)});say("Listo.",true);loadPend()}catch(e){say(e.message)}}
async function loadBrain(){try{const d=await api("/api/v1/brain?refresh=true");const b=$("brain");b.replaceChildren();
 b.append(el("div",{className:"st "+(d.local.ready?"ok":"aviso"),textContent:d.local.ready?"✔ Modelo local listo: lo privado corre en tu PC.":"▲ Sin modelo local: lo privado va por reglas y no sale a la nube."}));
 d.local.hints.forEach(h=>b.append(el("div",{className:"st aviso",textContent:"• "+h})));
 b.append(el("div",{className:"st info",textContent:"Solo local: "+d.private.join(", ")}));
 for(const [r,v] of Object.entries(d.roles))b.append(el("div",{className:"st",textContent:r+": "+v.tiers.join(" → ")+(v.now?"  ("+v.now+")":"")}))}catch(e){say(e.message)}}
function render(d){
 const c=$("checks");c.replaceChildren(...d.checks.map(i=>el("div",{className:"st "+i.status,textContent:({ok:"✔ ",falta:"✖ ",aviso:"▲ ",info:"• "})[i.status]+i.area+": "+i.text})));
 if(d.restart_needed.length)c.append(el("div",{className:"st aviso",textContent:"Hay que reiniciar Raphael para: "+d.restart_needed.join(", ")}));
 const g=$("groups");g.replaceChildren();
 for(const k of Object.keys(G)){const fs=d.fields.filter(f=>f.group===k);if(!fs.length)continue;
  const s=el("section",{className:"card"},el("h2",{textContent:G[k]}));
  for(const f of fs){const id="f_"+f.name;s.append(el("label",{htmlFor:id},f.label+" ",el("small",{textContent:f.help||""})));
   const inp=el("input",{id,type:f.secret?"password":"text",autocomplete:"off",placeholder:f.set?(f.secret?"cargada "+f.hint+" · escribí para reemplazarla":""):"sin cargar"});
   if(!f.secret&&f.value)inp.value=f.value;inp.dataset.name=f.name;inp.dataset.was=f.value||"";const row=el("div",{className:"row"},inp);
   if(f.set){const b=el("button",{className:"sec mini",textContent:"Quitar"});b.onclick=()=>save({},[f.name]);row.append(b)}
   s.append(row)}
  const b=el("button",{textContent:"Guardar",style:"margin-top:14px"});b.onclick=()=>{const set={};
   s.querySelectorAll("input").forEach(i=>{const v=i.value.trim();if(v&&v!==i.dataset.was)set[i.dataset.name]=v});save(set,[])};
  s.append(b);g.append(s)}}
async function save(set,clear){if(!Object.keys(set).length&&!clear.length){say("No cambiaste nada.");return}
 try{render(await api("/api/v1/config",{method:"PUT",body:JSON.stringify({set,clear})}));say("Guardado. Ya está aplicado.",true)}catch(e){say(e.message)}}
async function loadCfg(){try{render(await api("/api/v1/config"))}catch(e){say(e.message)}}
async function enter(){try{await api("/api/v1/summary");show(true);tab("hablar")}catch(e){show(false);if(tok)say(e.message)}}
$("go").onclick=async()=>{try{const d=await api("/api/v1/login",{method:"POST",body:JSON.stringify({key:$("k").value,device:"web"})});
 tok=d.token;try{sessionStorage.setItem("t",tok)}catch(e){}$("k").value="";enter()}catch(e){say(e.message)}};
$("k").onkeydown=e=>{if(e.key==="Enter")$("go").click()};
$("chk").onclick=async()=>{const k=$("nk").value;try{await api("/api/v1/config/clave",{method:"POST",body:JSON.stringify({key:k})});
 const d=await api("/api/v1/login",{method:"POST",body:JSON.stringify({key:k,device:"web"})});tok=d.token;try{sessionStorage.setItem("t",tok)}catch(e){}
 $("nk").value="";say("Clave cambiada.",true);loadCfg()}catch(e){say(e.message)}};
$("pairb").onclick=async()=>{try{const d=await api("/api/v1/phone/pair",{method:"POST"});const p=$("pair");p.replaceChildren();
 p.append(el("div",{textContent:"Código: "+d.code,style:"font-size:1.4rem;font-weight:700;letter-spacing:.1em"}),el("div",{className:"mut",textContent:"Vale "+Math.round(d.expires_in/60)+" minutos y una sola vez."}));
 if(d.qr_svg)p.append(el("img",{src:"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(d.qr_svg),alt:"QR de emparejamiento",style:"width:220px;background:#fff;padding:8px;margin-top:8px"}));
 else p.append(el("div",{className:"st aviso",textContent:"Sin imagen de QR (falta instalar segno). Escribí el código en la app. Enlace: "+d.payload}));
 if(!d.host)p.append(el("div",{className:"st aviso",textContent:"Falta la dirección para el celular (Configuración → Celular): el QR no lleva servidor."}))}catch(e){say(e.message)}};
$("out").onclick=async()=>{try{await api("/api/v1/logout",{method:"POST"})}catch(e){}tok=null;try{sessionStorage.removeItem("t")}catch(e){}show(false)};

const C={tema:"auto",rec:null,temas:{}};
async function capi(p,o={},raw){const h={};if(tok)h.Authorization="Bearer "+tok;if(!raw)h["Content-Type"]="application/json";Object.assign(h,o.headers||{});
 const r=await fetch(p,{...o,headers:h});if(r.status===401){tok=null;show(false)}const ct=r.headers.get("content-type")||"";
 const d=ct.includes("json")?await r.json():await r.text();if(!r.ok)throw new Error((d&&d.detail)||("Error "+r.status));return d}
const cn=()=>$("cneg").value;const hoy=()=>new Date().toLocaleDateString("sv");
function cmsg(t){$("cst").textContent=t}
async function loadCampo(sel){try{const d=await capi("/api/v1/campo");C.temas=d.temas;const s=$("cneg");const cur=sel||s.value;s.replaceChildren();
 d.negocios.forEach(n=>s.append(el("option",{value:n.id,textContent:n.nombre})));if(cur)s.value=cur;
 if(!d.negocios.length){cmsg("Creá el negocio con «Nuevo» para empezar.");return}
 const t=$("ctemas");t.replaceChildren();[["auto","Auto"],...Object.entries(d.temas)].forEach(([k,v])=>{const b=el("button",{className:"mini "+(k===C.tema?"":"sec"),textContent:v});b.onclick=()=>{C.tema=k;loadCampo()};t.append(b)});
 if(!d.voz)cmsg("Sin voz instalada: los audios se guardan y se transcriben cuando haya voz.");loadHoy()}catch(e){say(e.message)}}
async function loadHoy(){if(!cn())return;try{const d=await capi("/api/v1/campo/notas?negocio="+cn()+"&dia="+hoy());const h=$("choy");h.replaceChildren();
 if(!d.notas.length)h.append(el("p",{className:"mut",textContent:"Todavía no anotaste nada hoy."}));
 d.notas.slice().reverse().forEach(n=>{const ic={texto:"",voz:"🎤 ",foto:"📷 "}[n.fuente];
  h.append(el("div",{className:"st",textContent:n.hora+" · "+(C.temas[n.tema]||n.tema)+" · "+ic+(n.texto||(n.fuente==="voz"?"(audio sin transcribir)":"(foto)"))}))})}catch(e){say(e.message)}}
$("cneg").onchange=loadHoy;$("cnew").onclick=()=>$("cnewrow").classList.toggle("hide");
$("cmk").onclick=async()=>{try{const n=await capi("/api/v1/campo/negocios",{method:"POST",body:JSON.stringify({nombre:$("cnn").value})});$("cnn").value="";$("cnewrow").classList.add("hide");loadCampo(n.id)}catch(e){say(e.message)}};
$("csave").onclick=async()=>{const t=$("ctxt").value.trim();if(!t)return say("Escribí algo primero.");
 try{await capi("/api/v1/campo/nota",{method:"POST",body:JSON.stringify({negocio:cn(),texto:t,tema:C.tema})});$("ctxt").value="";say("Guardada.",true);loadHoy()}catch(e){say(e.message)}};
$("cfoto").onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const q="?negocio="+cn()+"&tema="+C.tema+"&texto="+encodeURIComponent($("ctxt").value.trim());
 await capi("/api/v1/campo/foto"+q,{method:"POST",body:f,headers:{"Content-Type":f.type||"image/jpeg"}},true);$("ctxt").value="";say("Foto guardada.",true);loadHoy()}catch(x){say(x.message)}e.target.value=""};
$("cmic").onclick=async()=>{if(C.rec){C.rec.stop();return}
 if(!navigator.mediaDevices||!window.MediaRecorder)return say("Este navegador no puede grabar (necesita https o localhost).");
 try{const st=await navigator.mediaDevices.getUserMedia({audio:true});const ch=[];const r=new MediaRecorder(st);C.rec=r;
  r.ondataavailable=e=>ch.push(e.data);$("cmic").textContent="⏹ Parar";
  r.onstop=async()=>{st.getTracks().forEach(t=>t.stop());C.rec=null;$("cmic").textContent="🎤 Grabar";const b=new Blob(ch,{type:r.mimeType||"audio/webm"});
   try{const n=await capi("/api/v1/campo/voz?negocio="+cn()+"&tema="+C.tema,{method:"POST",body:b,headers:{"Content-Type":b.type}},true);
    say(n.aviso||"Audio guardado y transcripto.",!n.aviso);loadHoy()}catch(x){say(x.message)}};r.start()}catch(x){say("No pude usar el micrófono: "+x.message)}};
$("ccl").onclick=async()=>{const cosas=["cc1","cc2","cc3"].map(i=>$(i).value.trim()).filter(Boolean);if(!cosas.length)return say("Escribí al menos una.");
 try{await capi("/api/v1/campo/cierre",{method:"POST",body:JSON.stringify({negocio:cn(),cosas})});["cc1","cc2","cc3"].forEach(i=>$(i).value="");say("Cierre guardado.",true);loadHoy()}catch(e){say(e.message)}};
function verRes(r){const L=[r.dia+" · "+r.total+" nota(s)"];if(r.ia)L.push("","Según la IA local:",r.texto_ia);
 else L.push("","Pérdidas ("+r.origen_perdidas+"):",...r.perdidas.map((p,i)=>(i+1)+". "+p));L.push("","Mirar mañana:",...r.mirar_manana.map(m=>"- "+m));if(r.solo_para_damian&&r.solo_para_damian.length)L.push("","Solo para vos (no va al dueño):",...r.solo_para_damian.map(m=>"- "+m));$("cout").textContent=L.join("\n")}
$("cres").onclick=async()=>{try{verRes(await capi("/api/v1/campo/resumen?negocio="+cn()))}catch(e){say(e.message)}};
$("cresia").onclick=async()=>{try{cmsg("Pensando en tu PC…");const r=await capi("/api/v1/campo/resumen?ia=true&negocio="+cn());cmsg(r.ia?"":"Sin modelo local prendido: resumen por reglas.");verRes(r)}catch(e){say(e.message)}};
$("cask").onclick=async()=>{const q=$("cq").value.trim();if(!q)return;try{const r=await capi("/api/v1/campo/preguntar",{method:"POST",body:JSON.stringify({negocio:cn(),pregunta:q})});
 const L=[r.respuesta,"","Coincidencias: "+r.coincidencias+(r.ia?"":" (sin IA local: solo búsqueda)")];Object.entries(r.por_dia).forEach(([d,n])=>L.push("  "+d+": "+n));$("cout").textContent=L.join("\n")}catch(e){say(e.message)}};
$("cexp").onclick=async()=>{try{$("cout").textContent=await capi("/api/v1/campo/expediente?negocio="+cn())}catch(e){say(e.message)}};
$("cdl").onclick=async()=>{try{const t=await capi("/api/v1/campo/expediente?negocio="+cn());const a=el("a",{href:URL.createObjectURL(new Blob([t],{type:"text/markdown"})),download:"expediente-"+cn()+".md"});a.click()}catch(e){say(e.message)}};
enter();
</script></main></body></html>
"""
