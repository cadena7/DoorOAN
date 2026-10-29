
(function(){
  const zone='America/Tijuana', target=document.getElementById('Ensenada_z189');
  try {
    const clock=new Intl.DateTimeFormat('es-MX',{timeZone:zone,hour:'numeric',minute:'2-digit',second:'2-digit',hour12:true});
    const date=new Intl.DateTimeFormat('es-MX',{timeZone:zone,weekday:'long',day:'numeric',month:'numeric',year:'numeric'});
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:zone,year:'numeric',month:'numeric',day:'numeric'});
    const solarTime=new Intl.DateTimeFormat('es-MX',{timeZone:zone,hour:'2-digit',minute:'2-digit',hour12:false});
    let lastDay='', solar='';
    function update(){
      const now=new Date(), fields={};
      parts.formatToParts(now).forEach(p=>{fields[p.type]=p.value;});
      const y=Number(fields.year), m=Number(fields.month), d=Number(fields.day), key=y+'-'+m+'-'+d;
      if(key!==lastDay){
        const base=Date.UTC(y,m-1,d), day=(base-Date.UTC(y,0,0))/86400000;
        const leap=y%4===0&&(y%100!==0||y%400===0);
        const g=2*Math.PI/(leap?366:365)*(day-1), rad=Math.PI/180;
        const eq=229.18*(0.000075+0.001868*Math.cos(g)-0.032077*Math.sin(g)-0.014615*Math.cos(2*g)-0.040849*Math.sin(2*g));
        const dec=0.006918-0.399912*Math.cos(g)+0.070257*Math.sin(g)-0.006758*Math.cos(2*g)+0.000907*Math.sin(2*g)-0.002697*Math.cos(3*g)+0.00148*Math.sin(3*g);
        const lat=31.87149*rad, lon=-116.60071;
        const ha=Math.acos(Math.cos(90.833*rad)/(Math.cos(lat)*Math.cos(dec))-Math.tan(lat)*Math.tan(dec))/rad;
        const noon=720-4*lon-eq;
        solar='Salida del Sol: '+solarTime.format(new Date(base+(noon-4*ha)*60000))+' · Puesta del Sol: '+solarTime.format(new Date(base+(noon+4*ha)*60000));
        lastDay=key;
      }
      target.replaceChildren(document.createTextNode(clock.format(now)),document.createElement('br'),document.createTextNode(date.format(now)),document.createElement('br'),document.createTextNode(solar));
      target.title='Horarios solares aproximados para Ensenada. Hora basada en el reloj de este dispositivo.';
    }
    update(); setInterval(update,1000);
  } catch(error){target.textContent='No se pudo calcular la hora; consulta el enlace de Ensenada.';}
})();


let audio=null, opened=false,alarmEnabled=true;
try{alarmEnabled=localStorage.getItem('door-alarm')!=='off';}catch(e){}
const alarmCheck=document.getElementById('alarm-enabled'),alarmNote=document.getElementById('alarm-note');
alarmCheck.checked=alarmEnabled;
async function unlockAudio(){if(!alarmEnabled)return;try{if(!audio)audio=new(window.AudioContext||window.webkitAudioContext)();await audio.resume();alarmNote.textContent=audio.state==='running'?'Alarma lista. Sonará cuando la puerta esté abierta.':'Toca la página para permitir el sonido.';}catch(e){alarmNote.textContent='Audio no disponible en este navegador.';}}
document.addEventListener('pointerdown',unlockAudio);
document.addEventListener('keydown',unlockAudio);
alarmCheck.onchange=()=>{alarmEnabled=alarmCheck.checked;try{localStorage.setItem('door-alarm',alarmEnabled?'on':'off');}catch(e){}if(alarmEnabled)unlockAudio();else alarmNote.textContent='Alarma silenciada en este navegador.';};
if(alarmEnabled)unlockAudio();else alarmNote.textContent='Alarma silenciada en este navegador.';
let commandActive=false, updating=false, requestChain=Promise.resolve();
const camera=document.getElementById('camera');
let cameraURL='',cameraLoading=false,cameraPending=false,cameraTimer=null;
function refreshCamera(afterCommand=false){
  if(!cameraURL)return;
  if(cameraLoading){if(afterCommand)cameraPending=true;return;}
  clearTimeout(cameraTimer);
  const url=new URL(cameraURL,window.location.href);
  url.searchParams.set('t',Date.now());
  cameraLoading=true;camera.src=url.href;
}
function cameraFinished(){
  cameraLoading=false;
  if(cameraPending){cameraPending=false;refreshCamera();return;}
  cameraTimer=setTimeout(()=>{if(commandActive)cameraFinished();else refreshCamera();},30000);
}
camera.addEventListener('load',cameraFinished);
camera.addEventListener('error',cameraFinished);
function deviceRequest(url,options={}){
  const job=requestChain.then(async()=>{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
    try{const r=await fetch(url,{...options,signal:controller.signal,cache:'no-store'});
      const text=await r.text();return {status:r.status,ok:r.ok,data:r.ok?JSON.parse(text):null};
    }finally{clearTimeout(timer);}
  });
  requestChain=job.catch(()=>{});return job;
}
function showDoor(state,busy){opened=state==='abierta';let el=document.getElementById('state');el.dataset.state=state;el.textContent='Puerta '+state+(busy?' — relé activo':'');}
let command=document.getElementById('command');
if(command)command.addEventListener('submit',async event=>{
  event.preventDefault();if(commandActive)return;commandActive=true;
  let button=document.getElementById('command-button'),message=document.getElementById('command-message');
  button.disabled=true;message.textContent='Enviando instrucción…';
  const id=Date.now().toString(36)+Math.random().toString(36).slice(2);
  try{
    const form=new URLSearchParams(new FormData(command));form.set('command_id',id);
    const r=await deviceRequest('/openclose',{method:'POST',headers:{'Accept':'application/json'},body:form});
    if(r.status!==202){message.textContent=r.status===503?'Cola llena; intenta más tarde.':r.status===403?'Acceso vencido; recarga la página.':'Instrucción rechazada.';return;}
    message.textContent='Recibido';
    const deadline=Date.now()+30000;
    while(Date.now()<deadline){
      await new Promise(resolve=>setTimeout(resolve,1000));
      const result=await deviceRequest('/api/command/'+id);
      if(!result.ok)throw Error('Resultado desconocido');
      const state=result.data;showDoor(state.puerta,state.activando);
      if(state.estado==='terminado'){message.textContent='Instrucción terminada.';refreshCamera(true);return;}
      if(state.estado==='fallido'){message.textContent='Ejecución interrumpida; comprueba la puerta antes de repetir.';return;}
      message.textContent=state.estado==='esperando'?'Esperando turno…':'Ejecutando…';
    }
    throw Error('Tiempo de seguimiento agotado');
  }catch(error){opened=false;message.textContent='Resultado desconocido; comprueba la puerta antes de repetir.';}
  finally{commandActive=false;button.disabled=false;}
});
async function update(){
  if(commandActive||updating)return;updating=true;
  try{const r=await deviceRequest('/api/status');if(!r.ok)throw Error();showDoor(r.data.estado,r.data.activando);}
  catch(error){opened=false;let el=document.getElementById('state');el.dataset.state='desconocida';el.textContent='Sin comunicación';}
  finally{updating=false;}
}
setInterval(()=>{if(alarmEnabled&&audio&&audio.state==='running'&&opened){let o=audio.createOscillator(),g=audio.createGain();g.gain.value=0.08;o.connect(g);g.connect(audio.destination);o.frequency.value=880;o.start();o.stop(audio.currentTime+0.2);}},2000);
setInterval(update,1500);update();

async function loadUI(){
  const response=await deviceRequest('/api/ui');
  if(!response.ok)throw Error('No se pudo cargar el acceso');
  const ui=response.data;
  cameraURL=ui.camera;refreshCamera();
  document.getElementById('command').hidden=!ui.can_command;
  document.getElementById('login').hidden=ui.can_command;
  document.getElementById('logout').hidden=!(ui.login_required&&ui.can_command);
  document.querySelectorAll('input[name="csrf"]').forEach(input=>{input.value=ui.csrf||'';});
}
loadUI().catch(()=>{document.getElementById('command-message').textContent='No se pudo cargar el acceso; recarga la página.';document.getElementById('command-message').hidden=false;});
