"""La pantalla de Configuración (una sola página, sin dependencias). Entra con la clave de la app y deja poner o sacar
las claves a voluntad. Habla con `/api/v1/config`; no guarda nada en el navegador salvo la sesión de la pestaña."""

PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Raphael · Configuración</title>
<style>
:root{--bg:#f6f5f2;--fg:#1d1c1a;--mut:#6b6862;--card:#fff;--bd:#dedbd4;--ac:#2f5d50;--ok:#2e7d4f;--wa:#a8660b;--er:#b3382c}
@media(prefers-color-scheme:dark){:root{--bg:#151513;--fg:#ecebe7;--mut:#a09d95;--card:#1f1f1c;--bd:#33322e;--ac:#7fb5a3;--ok:#6cc08b;--wa:#e0a24d;--er:#ef7d70}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:20px 16px 60px}h1{font-size:1.4rem;margin:.2em 0}h2{font-size:1.05rem;margin:0 0 .6em}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin:14px 0}
label{display:block;font-weight:600;margin-top:12px}small,.mut{color:var(--mut);font-weight:400}
input,select{width:100%;padding:10px;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--fg);font:inherit}
button{padding:10px 16px;border:0;border-radius:8px;background:var(--ac);color:var(--bg);font:inherit;font-weight:600;cursor:pointer}
button.sec{background:transparent;color:var(--fg);border:1px solid var(--bd)}button.mini{padding:4px 10px;font-size:.85rem}
.row{display:flex;gap:8px;align-items:center}.row input{flex:1}.st{font-size:.9rem;margin:2px 0}
.ok{color:var(--ok)}.aviso{color:var(--wa)}.falta{color:var(--er)}.info{color:var(--mut)}
#msg{position:sticky;top:0;padding:10px;border-radius:8px;margin:8px 0;display:none}#msg.e{background:var(--er);color:#fff;display:block}#msg.g{background:var(--ok);color:#fff;display:block}
.hide{display:none}
</style></head><body><main>
<h1>Raphael · Configuración</h1>
<div id="msg" role="status"></div>
<section id="login" class="card"><h2>Entrar</h2>
<label for="k">Clave de la app</label><input id="k" type="password" autocomplete="current-password">
<p class="mut">La primera vez, la clave está en la ventana de Raphael y en el archivo <code>clave-inicial.txt</code> de la carpeta de datos.</p>
<button id="go">Entrar</button></section>
<div id="app" class="hide">
<section class="card"><h2>Estado</h2><div id="checks"></div></section>
<div id="groups"></div>
<section class="card"><h2>Clave de la app</h2><label for="nk">Clave nueva <small>(mínimo 8 caracteres)</small></label>
<input id="nk" type="password" autocomplete="new-password"><p class="mut">Al cambiarla se cierran las demás sesiones.</p>
<button id="chk" class="sec">Cambiar clave</button></section>
<p><button id="out" class="sec">Salir</button></p></div>
<script>
const T={ia:"Inteligencia artificial",meta:"WhatsApp e Instagram (Meta)",red:"Dirección pública",tienda:"Tienda de la clienta (opcional)"};
const $=id=>document.getElementById(id);let tok=null;try{tok=sessionStorage.getItem("t")}catch(e){}
function say(t,ok){const m=$("msg");m.textContent=t;m.className=ok?"g":"e";clearTimeout(say.t);say.t=setTimeout(()=>m.className="",6000)}
async function api(p,o={}){const h={"Content-Type":"application/json"};if(tok)h.Authorization="Bearer "+tok;
 const r=await fetch(p,{...o,headers:h});let d={};try{d=await r.json()}catch(e){}
 if(r.status===401&&tok){tok=null;try{sessionStorage.removeItem("t")}catch(e){}show(false)}
 if(!r.ok)throw new Error(d.detail||("Error "+r.status));return d}
function show(on){$("login").classList.toggle("hide",on);$("app").classList.toggle("hide",!on)}
function el(t,a,...k){const e=document.createElement(t);Object.assign(e,a||{});k.forEach(x=>e.append(x));return e}
function render(d){
 const c=$("checks");c.replaceChildren(...d.checks.map(i=>el("div",{className:"st "+i.status},({ok:"✔ ",falta:"✖ ",aviso:"▲ ",info:"• "})[i.status]+i.area+": "+i.text)));
 if(d.restart_needed.length)c.append(el("div",{className:"st aviso"},"Para que tome efecto hay que reiniciar Raphael: "+d.restart_needed.join(", ")));
 const g=$("groups");g.replaceChildren();
 for(const k of Object.keys(T)){const fs=d.fields.filter(f=>f.group===k);if(!fs.length)continue;
  const s=el("section",{className:"card"},el("h2",{},T[k]));
  for(const f of fs){const id="f_"+f.name;s.append(el("label",{htmlFor:id},f.label+" ",el("small",{},f.help||"")));
   let inp;if(f.name==="META_MODE"){inp=el("select",{id});["mock","real"].forEach(v=>inp.append(el("option",{value:v,textContent:v})));inp.value=f.value||"mock"}
   else{inp=el("input",{id,type:f.secret?"password":"text",autocomplete:"off",placeholder:f.set?(f.secret?"cargada "+f.hint+" · escribí para reemplazarla":""):"sin cargar"});if(!f.secret&&f.value)inp.value=f.value}
   inp.dataset.name=f.name;inp.dataset.was=f.value||"";const row=el("div",{className:"row"},inp);
   if(f.set&&f.name!=="META_MODE"){const b=el("button",{className:"sec mini",textContent:"Quitar"});b.onclick=()=>save({},[f.name]);row.append(b)}
   s.append(row)}
  const b=el("button",{textContent:"Guardar",style:"margin-top:14px"});b.onclick=()=>{const set={};
   s.querySelectorAll("input,select").forEach(i=>{const v=i.value.trim();if(v&&v!==i.dataset.was)set[i.dataset.name]=v});save(set,[])};
  s.append(b);g.append(s)}}
async function save(set,clear){if(!Object.keys(set).length&&!clear.length){say("No cambiaste nada.");return}
 try{render(await api("/api/v1/config",{method:"PUT",body:JSON.stringify({set,clear})}));say("Guardado. Ya está aplicado.",true)}catch(e){say(e.message)}}
async function load(){try{render(await api("/api/v1/config"));show(true)}catch(e){show(false);if(tok)say(e.message)}}
$("go").onclick=async()=>{try{const d=await api("/api/v1/login",{method:"POST",body:JSON.stringify({key:$("k").value,device:"web"})});
 tok=d.token;try{sessionStorage.setItem("t",tok)}catch(e){}$("k").value="";load()}catch(e){say(e.message)}};
$("k").onkeydown=e=>{if(e.key==="Enter")$("go").click()};
$("chk").onclick=async()=>{const k=$("nk").value;try{await api("/api/v1/config/clave",{method:"POST",body:JSON.stringify({key:k})});
 const d=await api("/api/v1/login",{method:"POST",body:JSON.stringify({key:k,device:"web"})});tok=d.token;try{sessionStorage.setItem("t",tok)}catch(e){}
 $("nk").value="";say("Clave cambiada.",true);load()}catch(e){say(e.message)}};
$("out").onclick=async()=>{try{await api("/api/v1/logout",{method:"POST"})}catch(e){}tok=null;try{sessionStorage.removeItem("t")}catch(e){}show(false)};
if(tok)load();
</script></main></body></html>
"""
