import os
import time
import binascii
import asyncio
from microdot import Microdot, Response, Request
import config


def escape(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def clock_markup():
    # Hora del navegador y aproximación solar NOAA, sin scripts externos.
    return '''<section style="margin:28px auto;font-size:16px">
<a href="https://time.is/Ensenada" rel="nofollow">Hora local en Ensenada:</a><br>
<span id="Ensenada_z189"></span>
<noscript>Activa JavaScript para mostrar la hora y los datos solares.</noscript>
<script>
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
</script>
</section>''' 


def page(title, body):
    return Response('<!doctype html><html lang="es"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<title>DoorOAN</title><style>body{font:17px Arial,sans-serif;max-width:960px;'
                    'margin:0 auto;padding:48px 24px;background:white;color:#333;text-align:center;line-height:1.65}'
                    'h1{font-size:38px;font-weight:300;line-height:1.25;margin:0 auto 28px;max-width:850px}'
                    'img{max-width:100%;height:auto;display:block;margin:0 auto}'
                    '#state{display:inline-block;margin:0 0 24px;padding:3px 22px;border-radius:6px;background:#eef2f4}'
                    '#state[data-state="abierta"]{background:#fce6e3;color:#a72d20}'
                    '#state[data-state="cerrada"]{background:#e6f2e9;color:#28613c}'
                    '.caption{font-size:15px;margin:14px 0 25px}'
                    'button{font:13px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase;'
                    'border:1px solid #bbb;border-radius:28px;padding:15px 30px;background:white;cursor:pointer;margin:8px}'
                    'button:disabled{opacity:.5;cursor:wait}input{font:inherit;padding:10px;margin:5px;max-width:85%}'
                    '#command-message{display:block;font-size:14px}details{margin:18px auto;max-width:500px}'
                    'summary{cursor:pointer;font-size:14px;color:#666}.alarm-note{font-size:13px;color:#777}'
                    '@media(max-width:600px){body{padding:28px 16px}h1{font-size:27px}}'
                    'footer{margin-top:32px;padding-top:16px;border-top:1px solid #cbd5df;'
                    'font-size:14px;color:#526475;text-align:center}'
                    '</style><h1>' + escape(title) + '</h1>' + body +
                    '<footer>DoorOAN · Edgar Omar Cadena Zepeda · IA-UNAM-ENS</footer></html>',
                    headers={'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'})


def create_app(door):
    app = Microdot()
    app.max_connections = config.HTTP_MAX_CONNECTIONS
    app.request_timeout = config.HTTP_REQUEST_TIMEOUT_S
    app.handler_timeout = config.HTTP_HANDLER_TIMEOUT_S
    app.response_timeout = config.HTTP_RESPONSE_TIMEOUT_S
    app.close_timeout = config.HTTP_CLOSE_TIMEOUT_S
    Request.max_content_length = 2048
    Request.max_body_length = 2048
    Request.max_readline = 1024
    Request.max_header_length = 4096
    sessions = {}
    commands = [0]
    command_states = {}

    def token():
        return binascii.hexlify(os.urandom(24)).decode()

    public_csrf = token()

    def session(request):
        now = time.ticks_ms()
        for key in list(sessions):
            if time.ticks_diff(now, sessions[key][0]) >= config.SESSION_SECONDS * 1000:
                del sessions[key]
        return sessions.get(request.cookies.get('door_session'))

    def authorized(request):
        if not config.LOGIN_REQUIRED:
            return request.form and request.form.get('csrf') == public_csrf
        current = session(request)
        return current and request.form and request.form.get('csrf') == current[1]

    @app.get('/')
    @app.get('/index.html')
    async def home(request):
        current = session(request)
        body = '<p id="state">Leyendo puerta…</p>'
        body += '<img id="camera" alt="Webcam OAN" src="%s"><p class="caption">Imagen en tiempo real de la puerta de acceso del OAN-SPM</p>' % escape(config.DOOR_CAMERA)
        if current or not config.LOGIN_REQUIRED:
            csrf = current[1] if config.LOGIN_REQUIRED else public_csrf
            body += '<form id="command" method="post" action="/openclose"><input type="hidden" name="csrf" value="%s"><button id="command-button">Abrir / cerrar</button><span id="command-message"></span></form>' % csrf
            if config.LOGIN_REQUIRED:
                body += '<form method="post" action="/logoutuser"><input type="hidden" name="csrf" value="%s"><button>Cerrar sesión</button></form>' % csrf
        else:
            body += '<form method="post" action="/loginuser"><input name="username" placeholder="Usuario" required><input type="password" name="password" placeholder="Contraseña" required><button>Entrar</button></form>'
        body += clock_markup()
        body += '<details><summary>Opciones de sonido</summary><label><input id="alarm-enabled" type="checkbox" checked> Alarma sonora habilitada</label><p id="alarm-note" class="alarm-note">Si el navegador bloquea el audio, toca la página para permitirlo.</p></details>'
        body += '''<script>
let audio=null, opened=false,alarmEnabled=true;
try{alarmEnabled=localStorage.getItem('door-alarm')!=='off';}catch(e){}
const alarmCheck=document.getElementById('alarm-enabled'),alarmNote=document.getElementById('alarm-note');
alarmCheck.checked=alarmEnabled;
async function unlockAudio(){if(!alarmEnabled)return;try{if(!audio)audio=new(window.AudioContext||window.webkitAudioContext)();await audio.resume();alarmNote.textContent=audio.state==='running'?'Alarma lista. Sonará cuando la puerta esté abierta.':'Toca la página para permitir el sonido.';}catch(e){alarmNote.textContent='Audio no disponible en este navegador.';}}
document.addEventListener('pointerdown',unlockAudio);
document.addEventListener('keydown',unlockAudio);
alarmCheck.onchange=()=>{alarmEnabled=alarmCheck.checked;try{localStorage.setItem('door-alarm',alarmEnabled?'on':'off');}catch(e){}if(alarmEnabled)unlockAudio();else alarmNote.textContent='Alarma silenciada en este navegador.';};
if(alarmEnabled)unlockAudio();else alarmNote.textContent='Alarma silenciada en este navegador.';
let command=document.getElementById('command');
if(command)command.addEventListener('submit',async event=>{
event.preventDefault();let button=document.getElementById('command-button'),message=document.getElementById('command-message');
let id=Date.now().toString(36)+Math.random().toString(36).slice(2),pending=true,polling=false;
button.disabled=true;message.textContent='Enviando instrucción…';
let timer=setInterval(async()=>{if(polling)return;polling=true;try{let r=await fetch('/api/command/'+id,{cache:'no-store'});if(r.ok){let s=await r.json();if(pending)message.textContent=s.estado==='esperando'?'Esperando turno…':'Ejecutando…';}}catch(e){}finally{polling=false;}},500);
try{let form=new URLSearchParams(new FormData(command));form.set('command_id',id);let r=await fetch('/openclose',{method:'POST',body:form});pending=false;message.textContent=r.ok?'Instrucción terminada.':(r.status===503?'Cola llena; intenta más tarde.':r.status===403?'Acceso vencido; recarga la página.':'Error al ejecutar la instrucción.');}
catch(e){pending=false;message.textContent='Sin respuesta. Comprueba la puerta antes de repetir.';}
finally{pending=false;clearInterval(timer);button.disabled=false;update();}});
async function update(){try{let r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error();let s=await r.json();opened=s.estado==='abierta';let state=document.getElementById('state');state.dataset.state=s.estado;state.textContent='Puerta '+s.estado+(s.activando?' — relé activo':'');}catch(e){opened=false;let state=document.getElementById('state');state.dataset.state='desconocida';state.textContent='Sin comunicación';}}
setInterval(()=>{if(alarmEnabled&&audio&&audio.state==='running'&&opened){let o=audio.createOscillator(),g=audio.createGain();g.gain.value=0.08;o.connect(g);g.connect(audio.destination);o.frequency.value=880;o.start();o.stop(audio.currentTime+0.2);}},2000);
setInterval(update,1500);update();
setInterval(()=>{let i=document.getElementById('camera');i.src=i.src.split('?')[0]+'?t='+Date.now();},5000);
</script>'''
        return page('Sistema de Apertura y Cierre de Puerta Principal OAN-SPM', body)

    @app.get('/api/status')
    async def status(request):
        return {'estado': await door.state(), 'activando': door.busy}, 200, {'Cache-Control': 'no-store'}

    @app.get('/api/command/<command_id>')
    async def command_status(request, command_id):
        state = command_states.get(command_id)
        if state is None:
            return 'Instrucción no activa', 404
        return {'estado': state}, 200, {'Cache-Control': 'no-store'}

    @app.route('/loginuser', methods=['GET', 'POST'])
    async def login(request):
        if not config.LOGIN_REQUIRED or request.method == 'GET':
            return Response.redirect('/')
        form = request.form or {}
        if form.get('username', '').strip() != config.USERNAME or form.get('password', '') != config.PASSWORD:
            await asyncio.sleep_ms(1000)
            response = page('Acceso denegado', '<p>Usuario o contraseña incorrectos.</p>')
            response.status_code = 401
            return response
        session(request)
        old = request.cookies.get('door_session')
        sessions.pop(old, None)
        if len(sessions) >= config.MAX_SESSIONS:
            return 'Límite de sesiones alcanzado', 503
        key = token()
        sessions[key] = (time.ticks_ms(), token())
        response = Response.redirect('/')
        response.set_cookie('door_session', key, path='/',
                            max_age=config.SESSION_SECONDS, http_only=True)
        response.headers['Set-Cookie'][-1] += '; SameSite=Strict'
        return response

    @app.post('/logoutuser')
    async def logout(request):
        if not config.LOGIN_REQUIRED:
            return Response.redirect('/')
        if not authorized(request):
            return 'Acceso denegado', 403
        sessions.pop(request.cookies.get('door_session'), None)
        response = Response.redirect('/')
        response.delete_cookie('door_session', path='/')
        return response

    @app.post('/openclose')
    async def openclose(request):
        if not authorized(request):
            return 'Acceso denegado', 403
        if commands[0] >= config.MAX_PENDING_COMMANDS + 1:
            return 'Cola de mando llena; intentar más tarde', 503
        command_id = (request.form or {}).get('command_id')
        if command_id and (len(command_id) > 64 or command_id in command_states):
            return 'Identificador inválido o repetido', 400
        if command_id:
            command_states[command_id] = 'esperando'
        def started():
            if command_id:
                command_states[command_id] = 'ejecutando'
        commands[0] += 1
        try:
            await door.pulse(on_start=started)
        finally:
            commands[0] -= 1
            if command_id:
                command_states.pop(command_id, None)
        return Response.redirect('/')

    return app
