# Conexiones DoorOAN

Ver `conexiones.png`. El dibujo incluye dos pares separados, confirmados por
el usuario: mando del mecanismo y switch de estado.

La red utiliza el puerto RJ45 integrado: IP estática `132.248.4.210`, máscara
`255.255.255.0`, gateway `132.248.4.254`, DNS `8.8.8.8`. Desconectar la
BeagleBone que utiliza esa IP antes de conectar la Olimex a la misma red.
Acceso web: `http://132.248.4.210`, puerto HTTP 80; no hace falta escribir
`:80` en el navegador del teléfono o la computadora.

## Mando confirmado

Conectar los dos cables de mando a COM y NO de REL1 integrado en la Olimex.
No tienen polaridad. GPIO32 activa el relé durante cuatro segundos; NC queda
libre. Identificar COM/NO por la serigrafía o continuidad, no por su posición
en el dibujo. No conectar estos cables a los GPIO ni alimentar el motor
directamente con esta conexión.

## Estado mediante módulo externo: esquema condicionado a verificación

Enlace proporcionado: https://www.amazon.com.mx/dp/B01L1OI1HC

Amazon no permitió consultar directamente la ficha. Los catálogos que
referencian ese ASIN lo describen como Icstation EL817 con entrada de 12 V,
pero hay distintas variantes de entrada y circuitos de salida. No se pudo
verificar un esquema del fabricante correspondiente a la unidad concreta.
El PNG muestra la conexión funcional para terminales IN+/IN− y
VCC/OUT/GND; confirmar etiquetas y variante antes de conectarlo.

El usuario confirmó un switch Eaton NO de dos cables: el contacto cierra
cuando la puerta se abre. Sin activar (contacto abierto), el programa debe
interpretar puerta cerrada. Cablear ese único contacto de estado así:

- Fuente DC de campo aislada: positivo → un cable del switch; otro cable → IN+.
- Negativo de la fuente de campo → IN−.
- VCC del lado de salida → 3.3 V de Olimex, **si esa alimentación está admitida por el módulo**.
- GND del lado de salida → GND de Olimex.
- OUT → GPIO4 (UEXT TX), **solo después de verificar 0–3.3 V en ambas posiciones del switch**.

La tensión de campo debe corresponder a la entrada de la variante comprada:
12 V únicamente si esa unidad es de entrada 12 V. No conectar 12 V al
lado de salida ni al GPIO. No unir las tierras de campo y ESP32 si se busca
conservar el aislamiento; una fuente compartida sin aislamiento lo anula.

GPIO4 está configurado con pull-down interno (`SENSOR_PULL = "down"`),
para una salida activa alta. No usar UART1 en este pin. Hay módulos con
resistencias integradas y salidas de polaridad diferente: confirmar el
circuito. Si la salida es colector abierto que conduce a GND, puede necesitar
`SENSOR_PULL = "up"` en lugar de down y `SENSOR_CLOSED_LEVEL = 1`.
La resistencia interna es débil; la salida debe producir niveles estables
en el montaje real. Si requiere polarización externa, dimensionarla según
el circuito del módulo; cambiar de GPIO no modifica su topología.

Con el GPIO todavía desconectado, medir OUT respecto a GND del lado de
salida con el switch abierto y cerrado. Debe cambiar entre niveles lógicos
estables compatibles con 3.3 V. Si queda flotante o en un nivel intermedio,
revisar el circuito antes de conectar la placa.

Configurar `SENSOR_CLOSED_LEVEL` con el nivel medido cuando el switch está
SIN activar, con su contacto abierto (puerta cerrada): `0` si OUT es bajo,
o `1` si OUT es alto. El programa actual conserva `0`; no se cambió sin
confirmar la polaridad eléctrica del módulo. Al activar el switch (puerta
abierta), OUT debe pasar al nivel opuesto y la página indicar `abierta`.

Con este único contacto NO no se distingue puerta cerrada de un cable
del switch cortado/desconectado o de una pérdida de alimentación de campo:
todos pueden dejar el opto sin activar. La lectura es la interpretación
solicitada, no una confirmación independiente de cierre.

## Archivos de la computadora

`conexiones.png`, `conexiones.md` y `dibuja_conexiones.py` no se suben al
microcontrolador. Este último permite regenerar la imagen con Python y Pillow.

Fuentes: [esquema oficial de Olimex](https://github.com/OLIMEX/ESP32-EVB/blob/master/HARDWARE/REV-K1/ESP32-EVB_Rev_K1.sch),
[catálogo que identifica el ASIN](https://www.desertcart.ae/products/41227377-5-pcs-optocoupler-isolation-board-icstation-dc-12v-optocoupler-isolation),
[MicroPython ESP32](https://docs.micropython.org/en/latest/esp32/quickref.html).
