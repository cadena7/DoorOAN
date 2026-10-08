"""Arranque automático de DoorOAN en MicroPython ESP32."""
import sys
sys.path.append('/lib/microdot')
import time
import asyncio
import gc
import network
from machine import Pin
import config
from hardware import Door


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


async def supervise(app, watchdog):
    while True:
        await asyncio.sleep_ms(config.WATCHDOG_FEED_MS)
        if app.server is not None:
            gc.collect()
            if watchdog is not None:
                watchdog.feed()


async def serve(app):
    watchdog = None
    if config.WATCHDOG_ENABLED:
        from machine import WDT
        watchdog = WDT(timeout=config.WATCHDOG_TIMEOUT_MS)
    task = asyncio.create_task(supervise(app, watchdog))
    try:
        await app.start_server(host='0.0.0.0', port=config.HTTP_PORT)
    finally:
        task.cancel()


def main():
    door = Door()
    try:
        if config.LOGIN_REQUIRED and not config.PASSWORD:
            raise ValueError('Configura PASSWORD en config.py para habilitar el login')
        lan = connect()
        from webapp import create_app
        asyncio.run(serve(create_app(door)))
    finally:
        door.shutdown()


if __name__ == '__main__':
    main()
