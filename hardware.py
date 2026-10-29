import asyncio
from machine import Pin, Timer
import config


class Door:
    def __init__(self):
        self.relay = Pin(config.RELAY_GPIO, Pin.OUT, value=0)
        self.unused = Pin(config.UNUSED_RELAY_GPIO, Pin.OUT, value=0)
        if config.SENSOR_PULL not in ("down", "up"):
            raise ValueError('SENSOR_PULL debe ser down o up')
        pull = Pin.PULL_DOWN if config.SENSOR_PULL == "down" else Pin.PULL_UP
        self.sensor = Pin(config.SENSOR_GPIO, Pin.IN, pull)
        self.timer = Timer(0)
        self.busy = False
        self.command_lock = asyncio.Lock()

    def off(self, timer=None):
        self.relay.value(0)

    async def state(self):
        first = self.sensor.value()
        await asyncio.sleep_ms(config.DEBOUNCE_MS)
        second = self.sensor.value()
        if first != second:
            return "inestable"
        return "cerrada" if second == config.SENSOR_CLOSED_LEVEL else "abierta"

    async def pulse(self, on_start=None):
        async with self.command_lock:
            self.busy = True
            try:
                self.timer.init(period=config.PULSE_MS, mode=Timer.ONE_SHOT,
                                callback=self.off)
                self.relay.value(1)
                if on_start is not None:
                    on_start()
                await asyncio.sleep_ms(config.PULSE_MS)
            finally:
                self.off()
                self.timer.deinit()
                self.busy = False
            await asyncio.sleep_ms(config.PULSE_GAP_MS)
            return True

    def shutdown(self):
        self.off()
        self.unused.value(0)
        self.timer.deinit()
