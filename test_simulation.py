"""Pruebas de lógica en CPython; no certifican el hardware real."""
import asyncio
import sys
import time
import types
import re
import unittest
sys.path.insert(0, 'lib/microdot')
asyncio.sleep_ms = lambda ms: asyncio.sleep(ms / 1000)
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b


class Pin:
    OUT, IN = 1, 0
    PULL_DOWN, PULL_UP = 2, 3
    def __init__(self, number, mode, pull=None, value=1):
        self.number = number
        self.pull = pull
        self.level = value
        self.history = []
    def value(self, value=None):
        if value is not None:
            self.level = value
            self.history.append((time.monotonic(), value))
        return self.level


class Timer:
    ONE_SHOT = 0
    def __init__(self, number):
        self.handle = None
    def init(self, period, mode, callback):
        self.handle = asyncio.get_running_loop().call_later(period / 1000, callback, self)
    def deinit(self):
        if self.handle:
            self.handle.cancel()


sys.modules['machine'] = types.SimpleNamespace(Pin=Pin, Timer=Timer)
import config
from hardware import Door
from webapp import create_app
from microdot import Request


class Simulation(unittest.IsolatedAsyncioTestCase):
    async def test_flow(self):
        config.LOGIN_REQUIRED = True
        self.addCleanup(setattr, config, 'LOGIN_REQUIRED', False)
        config.PASSWORD = 'admin'
        config.PULSE_MS = 150
        door = Door()
        app = create_app(door)

        async def request(path, method='GET', form=None, cookie=None):
            req = Request(app, None, method, path, 'HTTP/1.1', {})
            req._form = form or {}
            if cookie:
                req.cookies['door_session'] = cookie
            return await app.dispatch_request(req)

        self.assertEqual(door.relay.value(), 0)
        self.assertEqual(door.sensor.number, 4)
        self.assertEqual(door.sensor.pull, Pin.PULL_DOWN)
        self.assertEqual((await request('/openclose')).status_code, 405)
        self.assertEqual((await request('/openclose', 'POST')).status_code, 403)
        self.assertEqual((await request('/loginuser', 'POST', {'username': 'admin', 'password': 'bad'})).status_code, 401)
        login = await request('/loginuser', 'POST', {'username': 'admin', 'password': config.PASSWORD})
        self.assertEqual(login.status_code, 302)
        cookie = login.headers['Set-Cookie'][0].split(';')[0].split('=')[1]
        home = await request('/', cookie=cookie)
        csrf = re.search('name="csrf" value="([^"]+)"', home.body.decode()).group(1)
        self.assertEqual((await request('/openclose', 'POST', {'csrf': 'bad'}, cookie)).status_code, 403)
        pending = asyncio.create_task(request('/openclose', 'POST', {'csrf': csrf, 'command_id': 'first'}, cookie))
        await asyncio.sleep(0.005)
        self.assertEqual(door.relay.value(), 1)
        queued = asyncio.create_task(request('/openclose', 'POST', {'csrf': csrf, 'command_id': 'second'}, cookie))
        await asyncio.sleep(0.005)
        self.assertFalse(queued.done())
        self.assertIn(b'ejecutando', (await request('/api/command/first')).body)
        self.assertIn(b'esperando', (await request('/api/command/second')).body)
        self.assertEqual((await pending).status_code, 302)
        self.assertIn(b'ejecutando', (await request('/api/command/second')).body)
        self.assertEqual((await queued).status_code, 302)
        self.assertEqual((await request('/api/command/second')).status_code, 404)
        highs = [stamp for stamp, level in door.relay.history if level == 1]
        self.assertEqual(len(highs), 2)
        self.assertGreaterEqual(highs[1] - highs[0], (config.PULSE_MS + config.PULSE_GAP_MS) / 1000)
        self.assertTrue(any(highs[0] < stamp < highs[1] and level == 0
                            for stamp, level in door.relay.history))
        self.assertEqual(door.relay.value(), 0)
        door.sensor.value(0)
        self.assertEqual(await door.state(), 'cerrada')
        door.sensor.value(1)
        self.assertEqual(await door.state(), 'abierta')
        self.assertEqual((await request('/api/status')).status_code, 200)
        for path in ('/cupulas.html', '/acerca.html'):
            self.assertEqual((await request(path)).status_code, 404)
        self.assertEqual((await request('/logoutuser', 'POST', {'csrf': csrf}, cookie)).status_code, 302)
        self.assertEqual((await request('/openclose', 'POST', {'csrf': csrf}, cookie)).status_code, 403)
        task = asyncio.create_task(door.pulse())
        await asyncio.sleep(0.005)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(door.relay.value(), 0)
        self.assertFalse(door.busy)
        door.shutdown()

    async def test_without_login(self):
        config.LOGIN_REQUIRED = False
        config.PASSWORD = ''
        config.PULSE_MS = 150
        door = Door()
        app = create_app(door)
        req = Request(app, None, 'GET', '/', 'HTTP/1.1', {})
        home = await app.dispatch_request(req)
        html = home.body.decode()
        self.assertIn('Abrir / cerrar', html)
        self.assertNotIn('name="password"', html)
        self.assertNotIn('<nav>', html)
        self.assertEqual(html.count('<img '), 1)
        self.assertIn("const zone='America/Tijuana'", html)
        self.assertNotIn('widget.time.is/es.js', html)
        self.assertIn('Salida del Sol:', html)
        csrf = re.search('name="csrf" value="([^"]+)"', html).group(1)
        req = Request(app, None, 'POST', '/openclose', 'HTTP/1.1', {})
        req._form = {'csrf': csrf}
        self.assertEqual((await app.dispatch_request(req)).status_code, 302)
        self.assertEqual(door.relay.value(), 0)
        async def send():
            req = Request(app, None, 'POST', '/openclose', 'HTTP/1.1', {})
            req._form = {'csrf': csrf}
            return await app.dispatch_request(req)
        pending = [asyncio.create_task(send()) for _ in range(3)]
        await asyncio.sleep(0.005)
        self.assertEqual((await send()).status_code, 503)
        results = await asyncio.gather(*pending)
        self.assertTrue(all(r.status_code == 302 for r in results))
        self.assertEqual((await send()).status_code, 302)
        active = asyncio.create_task(door.pulse())
        await asyncio.sleep(0.005)
        queued = asyncio.create_task(door.pulse())
        await asyncio.sleep(0.005)
        queued.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await queued
        self.assertEqual(door.relay.value(), 1)
        await active
        self.assertFalse(door.command_lock.locked())
        door.shutdown()


if __name__ == '__main__':
    unittest.main()
