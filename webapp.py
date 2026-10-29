import os
import time
import binascii
import asyncio
from lib.microdot.microdot import Microdot, Response, Request, send_file
import config


class LimitedReader:
    def __init__(self, reader):
        self.reader = reader
        self.header_bytes = 0

    async def readline(self):
        # Leer byte a byte limita memoria incluso con una línea sin salto final.
        line = bytearray()
        while True:
            char = await self.reader.read(1)
            if not char:
                break
            line.extend(char)
            self.header_bytes += len(char)
            if len(line) > Request.max_readline or self.header_bytes > 4096:
                raise ValueError('Cabeceras demasiado grandes')
            if char == b'\n':
                break
        return bytes(line)

    async def readexactly(self, size):
        return await self.reader.readexactly(size)


class DoorMicrodot(Microdot):
    """Protecciones locales; no dependen de modificar la biblioteca oficial."""
    def __init__(self):
        super().__init__()
        self.active_connections = 0
        self.command_tasks = set()

    async def stop_commands(self):
        for task in list(self.command_tasks):
            task.cancel()
        for task in list(self.command_tasks):
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def close_connection(self, writer):
        try:
            writer.close()
            if hasattr(writer, 'wait_closed'):
                await asyncio.wait_for(writer.wait_closed(), self.close_timeout)
            else:
                await asyncio.wait_for(writer.aclose(), self.close_timeout)
        except (OSError, asyncio.TimeoutError):
            pass

    async def handle_request(self, reader, writer):
        if self.active_connections >= self.max_connections:
            await self.close_connection(writer)
            return
        self.active_connections += 1
        response = None
        try:
            request = await asyncio.wait_for(
                Request.create(self, LimitedReader(reader), writer,
                               writer.get_extra_info('peername')),
                self.request_timeout)
            if request is None:
                return
            response = await asyncio.wait_for(self.dispatch_request(request),
                                              self.handler_timeout)
            if response is not Response.already_handled:
                await asyncio.wait_for(response.write(writer), self.response_timeout)
        except (asyncio.TimeoutError, OSError, ValueError):
            pass
        finally:
            # También liberar el archivo si hubo HEAD, timeout o desconexión.
            try:
                if response is not None and response is not Response.already_handled:
                    body = response.body
                    if hasattr(body, 'close'):
                        body.close()
            finally:
                try:
                    await self.close_connection(writer)
                finally:
                    self.active_connections -= 1


def create_app(door):
    app = DoorMicrodot()
    app.max_connections = config.HTTP_MAX_CONNECTIONS
    app.request_timeout = config.HTTP_REQUEST_TIMEOUT_S
    app.handler_timeout = config.HTTP_HANDLER_TIMEOUT_S
    app.response_timeout = config.HTTP_RESPONSE_TIMEOUT_S
    app.close_timeout = config.HTTP_CLOSE_TIMEOUT_S
    Request.max_content_length = 2048
    Request.max_body_length = 2048
    Request.max_readline = 1024
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

    def static_response(filename, content_type):
        response = send_file('static/' + filename, content_type=content_type)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Connection'] = 'close'
        return response

    @app.get('/')
    @app.get('/index.html')
    async def home(request):
        return static_response('index.html', 'text/html; charset=utf-8')

    @app.get('/static/<filename>')
    async def static(request, filename):
        # Lista cerrada: nunca construir rutas con nombres arbitrarios.
        types = {'app.js': 'application/javascript; charset=utf-8',
                 'style.css': 'text/css; charset=utf-8'}
        if filename not in types:
            return 'Not found', 404
        return static_response(filename, types[filename])

    @app.get('/api/ui')
    async def ui(request):
        current = session(request)
        csrf = current[1] if current and config.LOGIN_REQUIRED else public_csrf
        can_command = bool(current) or not config.LOGIN_REQUIRED
        return {'camera': config.DOOR_CAMERA, 'login_required': config.LOGIN_REQUIRED,
                'can_command': can_command, 'csrf': csrf if can_command else ''}, 200, {
                    'Cache-Control': 'no-store'}

    @app.get('/api/status')
    async def status(request):
        return {'estado': await door.state(), 'activando': door.busy}, 200, {'Cache-Control': 'no-store'}

    @app.get('/api/command/<command_id>')
    async def command_status(request, command_id):
        state = command_states.get(command_id)
        if state is None:
            return 'Instrucción no activa', 404
        if isinstance(state, dict):
            current = session(request)
            owner = current[1] if current and config.LOGIN_REQUIRED else public_csrf
            if (config.LOGIN_REQUIRED and not current) or owner != state['owner']:
                return 'Acceso denegado', 403
            return {'estado': state['estado'], 'puerta': await door.state(),
                    'activando': door.busy}, 200, {'Cache-Control': 'no-store'}
        return {'estado': state}, 200, {'Cache-Control': 'no-store'}

    @app.route('/loginuser', methods=['GET', 'POST'])
    async def login(request):
        if not config.LOGIN_REQUIRED or request.method == 'GET':
            return Response.redirect('/')
        form = request.form or {}
        if form.get('username', '').strip() != config.USERNAME or form.get('password', '') != config.PASSWORD:
            await asyncio.sleep_ms(1000)
            return Response('Usuario o contraseña incorrectos. <a href="/">Volver</a>',
                            401, {'Content-Type': 'text/html; charset=utf-8',
                                  'Cache-Control': 'no-store'})
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
        if request.headers.get('Accept') == 'application/json':
            command_id = (request.form or {}).get('command_id', '')
            if not command_id or len(command_id) > 64 or not all(
                    c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in command_id):
                return 'Identificador inválido', 400
            owner = request.form.get('csrf')
            now = time.ticks_ms()
            for key in list(command_states):
                record = command_states[key]
                if isinstance(record, dict) and record['estado'] in ('terminado', 'fallido') and time.ticks_diff(now, record['time']) >= 60000:
                    del command_states[key]
            previous = command_states.get(command_id)
            if previous is not None:
                if not isinstance(previous, dict) or previous['owner'] != owner:
                    return 'Identificador repetido', 400
                return {'estado': previous['estado']}, 202, {'Cache-Control': 'no-store'}
            if commands[0] >= config.MAX_PENDING_COMMANDS + 1 or len(command_states) >= 16:
                return 'Cola o historial lleno; intentar más tarde', 503
            record = {'estado': 'esperando', 'owner': owner, 'time': now}
            command_states[command_id] = record
            commands[0] += 1
            async def execute():
                def started():
                    record['estado'] = 'ejecutando'
                try:
                    await door.pulse(on_start=started)
                    record['estado'] = 'terminado'
                except asyncio.CancelledError:
                    record['estado'] = 'fallido'
                    raise
                except Exception:
                    record['estado'] = 'fallido'
                finally:
                    record['time'] = time.ticks_ms()
                    commands[0] -= 1
                    app.command_tasks.discard(task)
            try:
                task = asyncio.create_task(execute())
                app.command_tasks.add(task)
            except Exception:
                commands[0] -= 1
                command_states.pop(command_id, None)
                raise
            return {'estado': 'recibido'}, 202, {'Cache-Control': 'no-store'}
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
