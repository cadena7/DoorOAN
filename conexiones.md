# Conexiones DoorOAN

El sensor ahora usa GPIO17 (EXT1, señal GPIO17/SPI_CS), según el esquema
oficial de ESP32-EVB revisión K1. Reservar esa señal: no usar SPI en UEXT.
El diagrama `conexiones.png` conserva la etiqueta GPIO4 anterior; para OUT
aplica GPIO17 indicado aquí. El resto de las conexiones se conserva.
Comprobar la revisión y el pinout de la placa antes de cablear.

La red utiliza el puerto RJ45 integrado. Seleccionar en `config.py` el perfil
`lab` (por defecto, `192.168.0.210`, gateway `192.168.0.1`) o `final`.
El perfil final conserva IP estática `132.248.4.210`, máscara
`255.255.255.0`, gateway `132.248.4.254`, DNS `8.8.8.8`. Desconectar la
BeagleBone que utiliza esa IP antes de conectar la Olimex a la misma red.
Acceso web: `http://192.168.0.210` en laboratorio o `http://132.248.4.210`
en la red final, puerto HTTP 80; no hace falta escribir
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
- OUT → GPIO17 (EXT1 GPIO17/SPI_CS), **solo después de verificar 0–3.3 V en ambas posiciones del switch**.

La tensión de campo debe corresponder a la entrada de la variante comprada:
12 V únicamente si esa unidad es de entrada 12 V. No conectar 12 V al
lado de salida ni al GPIO. No unir las tierras de campo y ESP32 si se busca
conservar el aislamiento; una fuente compartida sin aislamiento lo anula.

GPIO17 usa pull-up interno (`SENSOR_PULL = "up"`). No usar SPI en UEXT
simultáneamente. Medición del módulo real comunicada por el usuario:
OUT = 3.2 V con opto sin activar y OUT = 0.10 V con opto activo.
La salida es activa baja y `SENSOR_CLOSED_LEVEL = 1` corresponde al switch
NO sin activar: puerta cerrada. Al cerrar el switch (puerta abierta),
OUT baja y la página indica `abierta`.
El dibujo anterior también conserva la indicación de pull-down; aplicar
el pull-up y GPIO17 de esta guía actualizada.

Con este único contacto NO no se distingue puerta cerrada de un cable
del switch cortado/desconectado o de una pérdida de alimentación de campo:
todos pueden dejar el opto sin activar. La lectura es la interpretación
solicitada, no una confirmación independiente de cierre.

## Archivos de la computadora

`conexiones.png` y `conexiones.md` no se suben al microcontrolador.

Fuentes: [esquema oficial de Olimex](https://github.com/OLIMEX/ESP32-EVB/blob/master/HARDWARE/REV-K1/ESP32-EVB_Rev_K1.sch),
[catálogo que identifica el ASIN](https://www.desertcart.ae/products/41227377-5-pcs-optocoupler-isolation-board-icstation-dc-12v-optocoupler-isolation),
[MicroPython ESP32](https://docs.micropython.org/en/latest/esp32/quickref.html).
