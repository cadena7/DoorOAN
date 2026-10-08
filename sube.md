# Archivos que debes subir al ESP32-EVB

Primero instala MicroPython para ESP32 clásico en la Olimex ESP32-EVB.
Después copia estos archivos al sistema de archivos del microcontrolador,
respetando exactamente esta estructura:

```text
/
├── main.py
├── config.py
├── hardware.py
├── webapp.py
└── lib/
    └── microdot/
        └── microdot.py
```

| Archivo en el micro | Función |
| --- | --- |
| `/main.py` | Arranca automáticamente, configura Ethernet estático e inicia el servidor en el puerto 80. |
| `/config.py` | Contiene IP/máscara/gateway/DNS, login opcional, GPIO, pulso y dirección de la cámara de puerta. |
| `/hardware.py` | Lee el sensor y controla el pulso del relé. |
| `/webapp.py` | Define las páginas, sesiones, control de puerta y alarma del navegador. El HTML y JavaScript están dentro de este archivo. |
| `/lib/microdot/microdot.py` | Biblioteca Microdot necesaria para el servidor web. Ya está incluida en esta carpeta. |

No subir `README.md`, `sube.md`, `test_simulation.py` ni `test_ethernet.py`: son documentación
y pruebas para la computadora. No se necesitan `boot.py`, plantillas HTML,
carpeta `static`, imágenes, MP3, Flask ni librerías de BeagleBone.
La imagen de la cámara de puerta se descarga directamente en el navegador.
Solo hay una página principal; no hay menú ni páginas adicionales.

## Antes de subir

Edita `config.py` en la computadora y configura:

```python
ETH_IP = "132.248.4.210"
ETH_NETMASK = "255.255.255.0"
ETH_GATEWAY = "132.248.4.254"
ETH_DNS = "8.8.8.8"
HTTP_PORT = 80
LOGIN_REQUIRED = False
USERNAME = "admin"
PASSWORD = "admin"
```

Los valores de red ya están tomados del archivo `Instalacion/network/interfaces`
del proyecto original (interfaz eth0). La dirección USB `192.168.7.2` de la
BeagleBone no se utiliza. No conectar BeagleBone y Olimex simultáneamente
con `132.248.4.210`: desconectar la anterior al sustituirla.

`LOGIN_REQUIRED = False` es el valor por defecto: el botón aparece sin pedir
usuario ni contraseña, y `PASSWORD` puede estar vacía. Para exigir login,
poner `LOGIN_REQUIRED = True` y configurar `USERNAME` y `PASSWORD`; en ese
modo solo la contraseña vacía impide arrancar. Se permite `admin / admin`
y son los valores por defecto. No se utiliza WiFi.

La configuración actual utiliza REL1 integrado en GPIO32 y el sensor en
GPIO4 (UEXT TX) a través del módulo optoacoplador externo, con pull-down
interno (`SENSOR_PULL = "down"`). No utilizar UART1 en ese pin.
El switch NO cierra al abrir la puerta; sin activar se interpreta puerta
cerrada. REL2 (GPIO33)
permanece apagado. Verificar alimentación y salida del módulo según
`conexiones.md`: `SENSOR_CLOSED_LEVEL` debe coincidir con el nivel de OUT
cuando el switch NO está SIN activar. El valor actual es 0; si en esa
condición se mide alto, cambiarlo a 1. Si la salida del módulo necesita
pull-up, configurar `SENSOR_PULL = "up"` tras verificar su circuito.

## Carga con Thonny

1. Selecciona el intérprete MicroPython (ESP32) y el puerto serie de la placa.
2. Copia los cuatro archivos `.py` de la raíz a la raíz del dispositivo.
3. Crea `/lib/microdot` en el dispositivo y copia allí `microdot.py`.
4. Conecta un cable RJ45 al Ethernet integrado y a la red OAN; reinicia la placa.
5. Revisa la consola serie: debe mostrar `DoorOAN: http://132.248.4.210`.
6. Abre esa dirección desde un equipo con acceso a la misma red. El botón
   aparece directamente; iniciar sesión solo si activaste `LOGIN_REQUIRED`.

Si cambias algún archivo, vuelve a copiarlo al mismo destino y reinicia
la placa. Un error de enlace Ethernet o de configuración se muestra en consola;
el relé queda apagado.

El firmware debe incluir `network.LAN` para el ESP32 clásico. Se configura
LAN8710A, dirección PHY 0, MDC GPIO23, MDIO GPIO18 y reloj externo de entrada
GPIO0, sin pin GPIO de alimentación. Esta configuración corresponde al
esquema ESP32-EVB revisado; no usar la de ESP32-POE o ESP32-GATEWAY.
Si no hay enlace después de 30 segundos, revisar el cable/switch y reiniciar.

## Si ya habías cargado la versión anterior

Para incorporar juntos los cambios de Ethernet, puerto 80 y sensor GPIO4,
vuelve a copiar `config.py`, `main.py` y `hardware.py` a la raíz del ESP32.
Conserva tu usuario y contraseña al actualizar `config.py`. Reinicia y abre
`http://132.248.4.210`, sin añadir puerto. El cable OUT del opto debe estar
en GPIO4 (UEXT TX), según el diagrama actualizado.

`webapp.py` y `/lib/microdot/microdot.py` siguen siendo necesarios; si ya
están cargados con esta versión del proyecto, estos cambios no requieren
volver a copiarlos. `conexiones.png`, `conexiones.md` y
`dibuja_conexiones.py` se quedan en la computadora.

Para el cambio de login opcional y ejecución de órdenes en espera, copiar
`config.py`, `main.py`, `hardware.py` y `webapp.py` y reiniciar.

## Botón e instrucciones simultáneas

Cada solicitud válida de abrir/cerrar espera hasta que termine la anterior.
El servidor ejecuta un pulso de cuatro segundos por solicitud y deja REL1
apagado 100 ms entre pulsos (`PULSE_GAP_MS`). Las órdenes no se ejecutan al
mismo tiempo. Se admite un mando activo y dos esperando; los adicionales
reciben HTTP 503 y no se ejecutan. El botón de esa página se
deshabilita al enviar y muestra «Enviando instrucción…», después «Esperando
turno…» solo si está en cola o «Ejecutando…» cuando inicia su propio pulso, hasta que
regresa la página. Las consultas de estado siguen disponibles durante el pulso.

Sin login, cualquier persona que pueda abrir la página puede usar el mando.
El token oculto del formulario sigue funcionando automáticamente y no pide
credenciales.

## Protección del servidor y archivos actualizados

Para watchdog y límites HTTP, subir `main.py`, `config.py`, `webapp.py` y
`lib/microdot/microdot.py`, conservando `hardware.py`, y reiniciar.
Watchdog activado por defecto: 8 segundos, alimentado cada segundo desde
el ciclo del servidor; recoge basura en esa misma tarea. Se activa después
de conectar Ethernet. Si el ciclo se bloquea o el servidor termina, reinicia.
No reinicia por falta de cable en el arranque ni detecta fallas del sensor.
Para depurar: `WATCHDOG_ENABLED = False` y reiniciar físicamente; un watchdog
ya iniciado no puede detenerse.

Se atienden hasta 6 conexiones; las adicionales se cierran. Timeout de
lectura 5 s, manejador 15 s, envío 5 s y cierre 1 s, configurables en
`config.py`. El manejador incluye el tiempo de espera del relé. Al vencer,
se cancela la solicitud: un pulso activo se apaga y una orden esperando no
se ejecuta. No repetir automáticamente una orden cuya respuesta se perdió,
porque pudo haber accionado el mecanismo. Cada conexión sirve una solicitud.
Cabeceras: 4 KiB; línea: 1 KiB; cuerpo: 2 KiB. La cola admite dos órdenes
además de la activa. Si se amplía, aumentar el timeout del manejador para
cubrir todos los pulsos y sus pausas. Validar estas protecciones en la placa.

## Cómo funciona la alarma sonora

El sonido sale de los altavoces de la computadora, teléfono o tableta que
abre la página. No hay buzzer conectado al ESP32.

1. La alarma está habilitada por defecto y trata de activar el audio al abrir
   la página. Si el navegador bloquea la reproducción automática, tocar la
   página o pulsar una tecla intenta desbloquearlo. No requiere login.
2. La página consulta `/api/status` cada 1.5 segundos para conocer el estado
   leído por el ESP32.
3. Mientras el estado sea `abierta`, genera un pitido de 880 Hz, de
   0.2 segundos de duración, cada 2 segundos.
4. Cuando una consulta indique `cerrada` o `inestable`, deja de emitir
   nuevos pitidos. Si falla la consulta, muestra **Sin comunicación** y
   también deja de emitirlos: el silencio no confirma que la puerta esté
   cerrada.

El sonido se genera mediante Web Audio en el navegador, sin archivos MP3
ni descargas de audio. La ganancia del programa es 0.08; el volumen final
también depende del volumen del dispositivo.

Al pie, abrir el desplegable **Opciones de sonido** y desmarcar **Alarma
sonora habilitada** para silenciarla; marcarla para reactivarla. La preferencia
se guarda en localStorage si está disponible, de forma independiente en cada
navegador. Tras recargar puede requerirse otro toque por las políticas de audio.
Accionar la puerta ahora envía el mando sin recargar la página y conserva
el audio desbloqueado. Cerrar la pestaña termina el sonido.

La distribución sigue la principal original: título centrado, indicador de
estado, cámara con su descripción, botón debajo y créditos al pie. Mantiene
la única cámara y página solicitadas. La webcam se actualiza cada 5 segundos.

Debajo del botón se muestra hora local y fecha de Ensenada usando la zona
`America/Tijuana`, con sus cambios de horario. El reloj se actualiza cada
segundo y usa la hora del teléfono o computadora; conviene tenerla automática.
La salida y puesta del sol se calculan en el navegador para cada fecha local,
con las coordenadas `31.8714900,-116.6007100` y las fórmulas aproximadas de
[NOAA](https://gml.noaa.gov/grad/solcalc/solareqns.PDF).
No necesita Internet ni scripts externos para esos datos, también en la
vista previa HTML. El enlace a Time.is queda como referencia. Los horarios
solares son aproximados y no consideran el relieve local. No usa el reloj
del ESP32. Para actualizar el dispositivo, vuelve a subir `webapp.py`.

Para usarla como aviso, deja abierta la página principal y verifica el
volumen del equipo. La pestaña en segundo plano o el dispositivo suspendido
pueden retrasar o detener los avisos. Es una alarma de la página web,
no una alarma física autónoma.
