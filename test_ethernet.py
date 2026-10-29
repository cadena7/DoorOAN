"""Pruebas simuladas de arranque Ethernet; ejecutar en CPython."""
import sys
import types
import unittest
import asyncio
from unittest.mock import patch
import test_simulation  # Instala machine y ticks simulados.


class LAN:
    def __init__(self, **kwargs):
        self.args = kwargs
        self.enabled = False
        self.address = None
    def active(self, enabled):
        self.enabled = enabled
    def ifconfig(self, address=None):
        if address is not None:
            self.address = address
        return self.address
    def isconnected(self):
        return True


fake_network = types.SimpleNamespace(LAN=LAN, PHY_LAN8710=1,
                                     PHY_LAN8720=2, ETH_CLOCK_GPIO0_IN=3)
sys.modules['network'] = fake_network
import main


class EthernetTest(unittest.TestCase):
    def test_static_network(self):
        # Los objetos Pin se sustituyen por números para inspeccionar asignaciones.
        with patch.object(main, 'Pin', new=PinStub), patch.multiple(
                main.config, ETH_IP='192.168.0.210', ETH_NETMASK='255.255.255.0',
                ETH_GATEWAY='192.168.0.1', ETH_DNS='8.8.8.8'):
            lan = main.connect()
        self.assertEqual(lan.address, ('192.168.0.210', '255.255.255.0',
                                      '192.168.0.1', '8.8.8.8'))
        self.assertEqual(lan.args, dict(mdc=23, mdio=18, phy_type=1,
                                       phy_addr=0, power=None,
                                       ref_clk=0, ref_clk_mode=0))
        self.assertTrue(lan.enabled)

    def test_old_constructor(self):
        def old_lan(**kwargs):
            if 'ref_clk' in kwargs:
                raise TypeError('unsupported keyword')
            return LAN(**kwargs)
        with patch.object(main, 'Pin', new=PinStub), patch.object(fake_network, 'LAN', old_lan):
            lan = main.connect()
        self.assertEqual(lan.args['clock_mode'], 3)
        self.assertEqual(lan.address[0], main.config.ETH_IP)

    def test_final_network(self):
        address = main.config.NETWORK_PROFILES['final']
        with patch.object(main, 'Pin', new=PinStub), patch.multiple(
                main.config, ETH_IP=address[0], ETH_NETMASK=address[1],
                ETH_GATEWAY=address[2], ETH_DNS=address[3]):
            lan = main.connect()
        self.assertEqual(lan.address, ('132.248.4.210', '255.255.255.0',
                                      '132.248.4.254', '8.8.8.8'))

    def test_no_link_disables_interface(self):
        lan = LAN()
        lan.isconnected = lambda: False
        with patch.object(main, 'Pin', new=PinStub), patch.object(fake_network, 'LAN', return_value=lan), patch.object(main.time, 'ticks_ms', side_effect=[0, 31000]):
            with self.assertRaisesRegex(RuntimeError, 'Sin enlace Ethernet'):
                main.connect()
        self.assertFalse(lan.enabled)


class PinStub:
    IN = 0
    def __new__(cls, number):
        return number


class ProtectionTest(unittest.IsolatedAsyncioTestCase):
    async def test_static_file_closes_on_head_and_send_timeout(self):
        import webapp
        from hardware import Door
        app = webapp.create_app(Door())
        files = []
        original = webapp.send_file
        def tracked(*args, **kwargs):
            response = original(*args, **kwargs)
            files.append(response.body)
            return response
        class Writer:
            def __init__(self, stalled=False):
                self.stalled = stalled
                self.closed = False
            def get_extra_info(self, key):
                return ('127.0.0.1', 1234)
            async def awrite(self, data):
                if self.stalled:
                    await asyncio.sleep(1)
            def close(self):
                self.closed = True
            async def wait_closed(self):
                pass
        with patch.object(webapp, 'send_file', tracked):
            app.response_timeout = 0.01
            for method, stalled in (('HEAD', False), ('GET', True)):
                reader = asyncio.StreamReader()
                reader.feed_data(('%s / HTTP/1.1\r\nHost: localhost\r\n\r\n' % method).encode())
                reader.feed_eof()
                writer = Writer(stalled)
                await app.handle_request(reader, writer)
                self.assertTrue(writer.closed)
                self.assertTrue(files[-1].closed)
                self.assertEqual(app.active_connections, 0)

    async def test_watchdog_feed_requires_server(self):
        watchdog = types.SimpleNamespace(feeds=0)
        def feed():
            watchdog.feeds += 1
        watchdog.feed = feed
        app = types.SimpleNamespace(server=None)
        with patch.object(main.config, 'WATCHDOG_FEED_MS', 5):
            task = asyncio.create_task(main.supervise(app, watchdog, LAN()))
            await asyncio.sleep(0.015)
            self.assertEqual(watchdog.feeds, 0)
            app.server = object()
            await asyncio.sleep(0.015)
            self.assertGreater(watchdog.feeds, 0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    async def test_http_limits_and_slow_reader(self):
        from hardware import Door
        from webapp import create_app
        app = create_app(Door())
        self.assertEqual(app.max_connections, 6)
        self.assertEqual(app.handler_timeout, 30)
        app.max_connections = 1
        app.request_timeout = 0.08
        server = await app.start_server(host='127.0.0.1', port=0, start_serving=False)
        await server.start_serving()
        port = server.sockets[0].getsockname()[1]
        writers = []
        async def assert_closed(reader):
            try:
                self.assertEqual(await asyncio.wait_for(reader.read(), 1), b'')
            except ConnectionResetError:
                pass  # Windows puede comunicar el cierre como reset de TCP.
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writers.append(writer)
            writer.write(b'GET / HTTP/1.1\r\n')
            await writer.drain()
            await asyncio.sleep(0.01)
            other_reader, other_writer = await asyncio.open_connection('127.0.0.1', port)
            writers.append(other_writer)
            await assert_closed(other_reader)
            await assert_closed(reader)
            await asyncio.sleep(0.01)
            self.assertEqual(app.active_connections, 0)
        finally:
            for writer in writers:
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionResetError:
                    pass
            server.close()
            await server.wait_closed()


class HealthTest(unittest.IsolatedAsyncioTestCase):
    async def run_supervisor(self, links, responses, steps):
        from unittest.mock import AsyncMock
        clock = [0]
        watchdog = types.SimpleNamespace(feeds=0)
        def feed():
            watchdog.feeds += 1
        watchdog.feed = feed
        async def sleep(ms):
            clock[0] += ms
            if clock[0] > steps * 1000:
                raise asyncio.CancelledError
        lan = types.SimpleNamespace(isconnected=lambda: links[(clock[0] - 1000) // 1000])
        probe = AsyncMock(side_effect=responses)
        with patch.object(main.time, 'ticks_ms', side_effect=lambda: clock[0]), patch.object(
                main.asyncio, 'sleep_ms', sleep), patch.object(main, 'http_healthy', probe), patch.multiple(
                main.config, WATCHDOG_FEED_MS=1000, ETH_LINK_TIMEOUT_S=3,
                HTTP_HEALTH_INTERVAL_S=2, HTTP_HEALTH_FAILURES=3):
            try:
                await main.supervise(types.SimpleNamespace(server=object()), watchdog, lan)
            except asyncio.CancelledError:
                pass
        return watchdog.feeds, probe.await_count, clock[0]

    async def test_persistent_link_loss_stops_feeding(self):
        feeds, probes, now = await self.run_supervisor([False] * 8, [True] * 8, 8)
        self.assertEqual((feeds, now), (3, 4000))

    async def test_brief_link_loss_recovers(self):
        feeds, probes, now = await self.run_supervisor(
            [False, False, True, False, False, True], [True] * 3, 6)
        self.assertEqual(feeds, 6)

    async def test_three_http_failures_stop_feeding(self):
        feeds, probes, now = await self.run_supervisor([True] * 8, [False] * 3, 8)
        self.assertEqual((feeds, probes, now), (5, 3, 6000))

    async def test_http_success_clears_failure_count(self):
        feeds, probes, now = await self.run_supervisor(
            [True] * 10, [False, False, True, False, False], 10)
        self.assertEqual((feeds, probes), (10, 5))

    async def test_real_page_probe_and_missing_page(self):
        from hardware import Door
        from webapp import create_app
        app = create_app(Door())
        server = await app.start_server(host='127.0.0.1', port=0, start_serving=False)
        await server.start_serving()
        port = server.sockets[0].getsockname()[1]
        try:
            with patch.object(main.config, 'HTTP_PORT', port):
                self.assertTrue(await main.http_healthy())
                with patch('webapp.send_file', side_effect=OSError('missing index')):
                    self.assertFalse(await main.http_healthy())
        finally:
            server.close()
            await server.wait_closed()

    async def test_stalled_probe_times_out_and_closes(self):
        from unittest.mock import AsyncMock
        writer = types.SimpleNamespace(write=lambda data: None, drain=AsyncMock(),
                                       close=unittest.mock.Mock(), wait_closed=AsyncMock())
        async def stalled(n):
            await asyncio.sleep(1)
        reader = types.SimpleNamespace(readexactly=stalled)
        with patch.object(main.asyncio, 'open_connection', AsyncMock(return_value=(reader, writer))), patch.object(
                main.config, 'HTTP_HEALTH_TIMEOUT_S', 0.01):
            self.assertFalse(await main.http_healthy())
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
