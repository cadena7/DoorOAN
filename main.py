"""Arranque automático de DoorOAN en MicroPython ESP32."""
import gc
# Recoger temporales durante las importaciones, antes de ampliar el heap.
if hasattr(gc, 'threshold'):
    gc.threshold(16 * 1024)
import time
import asyncio
import network
from machine import Pin
import config
from hardware import Door


def memory_status(stage):
    gc.collect()
    if hasattr(gc, 'mem_free'):
        print('Memoria Python libre (%s):' % stage, gc.mem_free())
    try:
        import esp32
    except ImportError:
        return
    print('Memoria IDF total/libre/bloque mayor/mínimo (%s):' % stage,
          esp32.idf_heap_info(esp32.HEAP_DATA))


def connect():
    if not hasattr(network, 'LAN'):
        raise RuntimeError('El firmware MicroPython necesita soporte network.LAN para ESP32')
    # LAN8710 y LAN8720 comparten el driver en versiones anteriores.
    phy_type = getattr(network, 'PHY_LAN8710', None)
    if phy_type is None:
        phy_type = network.PHY_LAN8720
    args = dict(mdc=Pin(config.ETH_MDC_GPIO), mdio=Pin(config.ETH_MDIO_GPIO),
                phy_type=phy_type, phy_addr=config.ETH_PHY_ADDR, power=None)
    try:
        lan = network.LAN(ref_clk=Pin(config.ETH_REF_CLK_GPIO),
                          ref_clk_mode=Pin.IN, **args)
    except TypeError:
        # API antigua: reloj GPIO0 de entrada configurado por clock_mode.
        lan = network.LAN(clock_mode=network.ETH_CLOCK_GPIO0_IN, **args)
    try:
        lan.active(True)
        lan.ifconfig((config.ETH_IP, config.ETH_NETMASK,
                      config.ETH_GATEWAY, config.ETH_DNS))
        start = time.ticks_ms()
        print('Esperando enlace Ethernet...')
        while not lan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > config.NETWORK_TIMEOUT_S * 1000:
                raise RuntimeError('Sin enlace Ethernet; revisar cable RJ45 y switch de red')
            time.sleep_ms(100)
        print('Ethernet IP/máscara/gateway/DNS:', lan.ifconfig())
        suffix = '' if config.HTTP_PORT == 80 else ':' + str(config.HTTP_PORT)
        print('DoorOAN: http://%s%s' % (lan.ifconfig()[0], suffix))
        return lan
    except Exception:
        lan.active(False)
        raise


async def http_healthy():
    """Comprueba la página local sin descargar HTML ni consultar el sensor."""
    writer = None
    async def request():
        nonlocal writer
        reader, writer = await asyncio.open_connection('127.0.0.1', config.HTTP_PORT)
        writer.write(b'HEAD / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        await writer.drain()
        status = await reader.readexactly(12)
        return status in (b'HTTP/1.0 200', b'HTTP/1.1 200')
    try:
        return await asyncio.wait_for(request(), config.HTTP_HEALTH_TIMEOUT_S)
    except (OSError, asyncio.TimeoutError, EOFError):
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), config.HTTP_CLOSE_TIMEOUT_S)
            except (OSError, asyncio.TimeoutError):
                pass


async def supervise(app, watchdog, lan):
    link_lost = None
    last_check = time.ticks_ms()
    failures = 0
    while True:
        await asyncio.sleep_ms(config.WATCHDOG_FEED_MS)
        now = time.ticks_ms()
        if not lan.isconnected():
            if link_lost is None:
                link_lost = now
                print('Supervisión: enlace Ethernet perdido')
            if time.ticks_diff(now, link_lost) >= config.ETH_LINK_TIMEOUT_S * 1000:
                print('Supervisión: Ethernet sin enlace; se deja vencer el watchdog')
                return
        else:
            if link_lost is not None:
                print('Supervisión: enlace Ethernet recuperado')
            link_lost = None
        if time.ticks_diff(now, last_check) >= config.HTTP_HEALTH_INTERVAL_S * 1000:
            healthy = app.server is not None and await http_healthy()
            last_check = time.ticks_ms()
            failures = 0 if healthy else failures + 1
            if not healthy:
                print('Supervisión: fallo HTTP local', failures, '/', config.HTTP_HEALTH_FAILURES)
            if failures >= config.HTTP_HEALTH_FAILURES:
                print('Supervisión: servidor sin respuesta; se deja vencer el watchdog')
                return
        if app.server is not None:
            gc.collect()
            if watchdog is not None:
                watchdog.feed()


async def serve(app, lan):
    watchdog = None
    if config.WATCHDOG_ENABLED:
        from machine import WDT
        watchdog = WDT(timeout=config.WATCHDOG_TIMEOUT_MS)
    task = asyncio.create_task(supervise(app, watchdog, lan))
    try:
        await app.start_server(host='0.0.0.0', port=config.HTTP_PORT)
    finally:
        task.cancel()
        await app.stop_commands()


def main():
    door = Door()
    lan = None
    try:
        if config.LOGIN_REQUIRED and not config.PASSWORD:
            raise ValueError('Configura PASSWORD en config.py para habilitar el login')
        memory_status('antes de Ethernet')
        lan = connect()
        memory_status('Ethernet activo, antes de Microdot')
        from lib.microdot.microdot import Microdot
        memory_status('Microdot cargado')
        from webapp import create_app
        app = create_app(door)
        memory_status('antes del servidor')
        asyncio.run(serve(app, lan))
    finally:
        door.shutdown()
        if lan is not None:
            lan.active(False)
        memory_status('servidor detenido')


if __name__ == '__main__':
    main()
