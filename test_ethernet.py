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
        with patch.object(main, 'Pin', new=PinStub):
            lan = main.connect()
        self.assertEqual(lan.address, ('132.248.4.210', '255.255.255.0',
                                      '132.248.4.254', '8.8.8.8'))
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
        self.assertEqual(lan.address[0], '132.248.4.210')

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
    async def test_watchdog_feed_requires_server(self):
        watchdog = types.SimpleNamespace(feeds=0)
        def feed():
            watchdog.feeds += 1
        watchdog.feed = feed
        app = types.SimpleNamespace(server=None)
        with patch.object(main.config, 'WATCHDOG_FEED_MS', 5):
            task = asyncio.create_task(main.supervise(app, watchdog))
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
        self.assertEqual(app.handler_timeout, 15)
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


if __name__ == '__main__':
    unittest.main()
