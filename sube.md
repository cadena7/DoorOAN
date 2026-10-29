# Archivos que debes subir ahora al ESP32-EVB

El proyecto usa **ocho archivos**, sin compilación previa ni copias de carga.
Copia los archivos originales respetando estos destinos:

| Archivo de la computadora | Destino en la placa | Función |
| --- | --- | --- |
| `main.py` | `/main.py` | Arranque, Ethernet, servidor y diagnóstico de memoria. |
| `config.py` | `/config.py` | Perfil de red, GPIO, login y tiempos. |
| `hardware.py` | `/hardware.py` | Sensor y relés. |
| `webapp.py` | `/webapp.py` | Sesiones, mandos y rutas de archivos estáticos. |
| `lib/microdot/microdot.py` | `/lib/microdot/microdot.py` | Biblioteca del servidor web. |
| `static/index.html` | `/static/index.html` | Página web. |
| `static/style.css` | `/static/style.css` | Estilo de la página. |
| `static/app.js` | `/static/app.js` | Estado, mando, cámara, reloj y alarma. |

La estructura final de la placa debe ser:

```text
/
├── main.py
├── config.py
├── hardware.py
├── webapp.py
├── lib/
│   └── microdot/
│       └── microdot.py
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

Si ya cargaste la versión compilada, después de copiar los `.py` elimina
solo de la placa `/hardware.mpy`, `/webapp.mpy` y
`/lib/microdot/microdot.mpy` si existen. Ya no forman parte de la carga.

No subir guías, pruebas, `conexiones.png` ni cachés. No se requiere un
`boot.py` de este proyecto. La carpeta `static/` sí es necesaria: se sirve
en fragmentos de hasta 1 KB, siguiendo el patrón de Energia2m. La cámara
se consulta directamente desde el navegador. Ethernet se activa antes de
importar `webapp` y Microdot.

## Antes de subir

Edita `config.py` en la computadora y configura:

```python
NETWORK_PROFILE = "lab"  # "final" para la red OAN.
HTTP_PORT = 80
LOGIN_REQUIRED = False
USERNAME = "admin"
PASSWORD = "admin"
```

El perfil `lab` usa `192.168.0.210`, máscara `255.255.255.0`, gateway
`192.168.0.1` y DNS `8.8.8.8`; comprobar que la IP esté libre y que el gateway
corresponda a tu router. El perfil `final` conserva los valores del archivo
`Instalacion/network/interfaces` del proyecto original (interfaz eth0).
La dirección USB `192.168.7.2` de la
BeagleBone no se utiliza. No conectar BeagleBone y Olimex simultáneamente
con `132.248.4.210`: desconectar la anterior al sustituirla.

`LOGIN_REQUIRED = False` es el valor por defecto: el botón aparece sin pedir
usuario ni contraseña, y `PASSWORD` puede estar vacía. Para exigir login,
poner `LOGIN_REQUIRED = True` y configurar `USERNAME` y `PASSWORD`; en ese
modo solo la contraseña vacía impide arrancar. Se permite `admin / admin`
y son los valores por defecto. No se utiliza WiFi.

La configuración actual utiliza REL1 en GPIO32 y OUT del opto en GPIO17
(EXT1 GPIO17/SPI_CS), con pull-up (`SENSOR_PULL = "up"`). No utilizar SPI en
UEXT en ese pin. REL2 (GPIO33) permanece apagado.
OUT mide 3.2 V sin activar el opto y 0.10 V al activarlo. El switch NO
cierra al abrir la puerta: `SENSOR_CLOSED_LEVEL = 1` interpreta alto como
cerrada y bajo como abierta. Para esta corrección subir `config.py` y reiniciar.

## Carga con Thonny

1. Selecciona MicroPython (ESP32) y el puerto serie de la placa.
2. Copia `main.py`, `config.py`, `hardware.py` y `webapp.py` a la raíz
   de la placa, y las carpetas `lib` y `static` con la estructura indicada.
3. Si habías cargado archivos `.mpy`, retira de la placa los tres indicados
   arriba después de copiar sus versiones `.py`.
4. Conecta RJ45 a la red elegida y corta/restablece alimentación.
5. Revisa la consola: muestra `DoorOAN: http://192.168.0.210` en laboratorio
   o `DoorOAN: http://132.248.4.210` con el perfil `final`.
6. Abre esa dirección desde un equipo de la misma red. Comprueba las líneas
   de memoria IDF y si reaparece `esp.emac: no mem for receive buffer`.
   La adaptación a archivos estáticos aún debe verificarse en la placa. Prueba el pulso primero sin conectar el controlador.

El firmware debe incluir `network.LAN` para ESP32 clásico. La configuración
actual es LAN8710A, PHY 0, MDC GPIO23, MDIO GPIO18 y reloj externo de entrada
GPIO0, sin pin de alimentación. Los pines de Energia2m están configurados de forma distinta; verificar
la revisión y el cableado antes de cambiar esta configuración. Si no hay enlace en 30 segundos, revisar
cable/switch y reiniciar.

## Cuando cambies archivos

Edita el archivo original en la computadora, cópialo al mismo destino
indicado en la tabla y reinicia la placa. No hay que compilar ni regenerar
una carpeta de carga. Para cambiar red o credenciales basta actualizar
`/config.py`; para cambiar la interfaz actualiza los archivos de `/static`.

Si aparece un error de importación, comprobar la existencia de
`/lib/microdot/microdot.py` y `/webapp.py`. La importación sigue siendo
`from lib.microdot.microdot import Microdot, Response, Request, send_file`.

## Botón e instrucciones simultáneas

Para esta actualización subir `main.py`, `webapp.py` y `static/app.js`,
y reiniciar físicamente. No se generan `.mpy` ni se modifica Microdot.

El botón envía un identificador único y recibe HTTP 202 («Recibido») sin
esperar los cuatro segundos del pulso. La ejecución continúa separada de
la conexión HTTP. Recibido no significa que el pulso haya terminado.
La página consulta el resultado una vez por segundo; esa respuesta incluye
estado de puerta y relé. Durante el mando se pausa la consulta normal de
estado. Las solicitudes al ESP32 se serializan y tienen timeout de 5 segundos.
El seguimiento termina a los 30 segundos o ante una respuesta perdida,
mostrando «Resultado desconocido; comprueba la puerta antes de repetir».
Nunca se reenvía automáticamente un mando.

Se conserva un mando activo y dos esperando; los adicionales reciben 503.
Los pulsos no se solapan y tienen una pausa de 4 segundos, igual al pulso. El resultado permanece
60 segundos en RAM; hay un máximo de 16 registros. Mientras esté registrado,
repetir el mismo identificador y token devuelve su estado sin ejecutar otro
pulso. Esta protección no persiste al reiniciar ni después de expirar el registro.
Con login, solo la sesión propietaria puede consultar su resultado.
Al detenerse el servidor se cancelan las tareas de mando; los pulsos activos
apagan el relé mediante su bloque `finally`.
Las solicitudes sin `Accept: application/json` conservan el comportamiento
anterior de esperar el pulso y redirigir a la página.

Sin login, cualquier persona que pueda abrir la página puede usar el mando.
El token del formulario no es una contraseña.

## Protección del servidor y archivos actualizados

Se utiliza la biblioteca Microdot oficial sin modificaciones. Los límites
HTTP y el cierre de archivos están implementados en `webapp.py` mediante
`DoorMicrodot`; no dependen de atributos que Microdot oficial no utiliza.
Después de actualizar la biblioteca, copiar también `/webapp.py` y
cortar/restablecer alimentación. La actualización restaura los docstrings
oficiales; el uso de memoria debe volver a comprobarse en la placa.

Si aparece `esp.emac: no mem for receive buffer`, el controlador Ethernet
no puede reservar memoria de recepción. El arranque actualizado activa Ethernet antes de cargar la
aplicación y recoge temporales desde las
importaciones. Imprime memoria Python y regiones IDF antes del enlace y del
servidor; los valores IDF son total, libre, bloque libre mayor y mínimo histórico.
Son una ayuda de diagnóstico, no una garantía de resolver el fallo.
Cargar los ocho archivos indicados al inicio y reiniciar físicamente. Si persiste, conservar esas líneas
junto al error para revisar memoria nativa y firmware. Para obtener el error
sin el reinicio posterior del watchdog, usar temporalmente
`WATCHDOG_ENABLED = False` en `config.py` y cortar/restablecer alimentación.
Restaurar `True` al terminar las pruebas. Si termina el servidor, el programa
apaga los relés y desactiva Ethernet.

Para actualizar watchdog y límites HTTP, usar también la misma lista de
ocho archivos; copiar los `.py` y la carpeta `static` actualizados.
Watchdog activado por defecto: 8 segundos, alimentado cada segundo desde
el ciclo del servidor; recoge basura en esa misma tarea. Se activa después
de conectar Ethernet. Si el ciclo se bloquea o el servidor termina, reinicia.
No reinicia por falta de cable en el arranque ni detecta fallas del sensor.
Para depurar: `WATCHDOG_ENABLED = False` y reiniciar físicamente; un watchdog
ya iniciado no puede detenerse.

Se atienden hasta 6 conexiones; las adicionales se cierran. Timeout de
lectura 5 s, manejador 30 s, envío 5 s y cierre 1 s, configurables en
`config.py`. Para el botón actual el manejador solo acepta el mando; el pulso sigue
en otra tarea. Las solicitudes de formularios sin JSON sí esperan el relé. Al vencer,
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
la única cámara y página solicitadas. La webcam espera 30 segundos entre
cargas en reposo y se actualiza una vez al confirmarse que terminó un mando.
No inicia otra carga mientras haya una pendiente; si termina el mando en
ese momento, la actualización se hace al finalizar la imagen en curso.
Para este cambio subir únicamente `static/app.js` y recargar la página.

Debajo del botón se muestra hora local y fecha de Ensenada usando la zona
`America/Tijuana`, con sus cambios de horario. El reloj se actualiza cada
segundo y usa la hora del teléfono o computadora; conviene tenerla automática.
La salida y puesta del sol se calculan en el navegador para cada fecha local,
con las coordenadas `31.8714900,-116.6007100` y las fórmulas aproximadas de
[NOAA](https://gml.noaa.gov/grad/solcalc/solareqns.PDF).
No necesita Internet ni scripts externos para esos datos.
El enlace a Time.is queda como referencia. Los horarios
solares son aproximados y no consideran el relieve local. No usa el reloj
del ESP32. Para actualizar el reloj o la alarma, copiar `/static/app.js`.

Para usarla como aviso, deja abierta la página principal y verifica el
volumen del equipo. La pestaña en segundo plano o el dispositivo suspendido
pueden retrasar o detener los avisos. Es una alarma de la página web,
no una alarma física autónoma.


## Vigilancia de Ethernet y servidor

Con `WATCHDOG_ENABLED = True`, la supervisión existente revisa el enlace
Ethernet cada segundo. Un corte continuo de `ETH_LINK_TIMEOUT_S = 30`
segundos deja de alimentar el watchdog. Si vuelve el enlace antes del límite,
el temporizador de desconexión se borra.

Cada `HTTP_HEALTH_INTERVAL_S = 15` segundos hace una petición `HEAD /` a
`127.0.0.1` en `HTTP_PORT`, para comprobar que la página principal devuelve
HTTP 200 sin descargar su HTML ni accionar relés. La petición tiene un límite
de `HTTP_HEALTH_TIMEOUT_S = 2` segundos, más hasta `HTTP_CLOSE_TIMEOUT_S`
para cerrar la conexión. Tras `HTTP_HEALTH_FAILURES = 3` fallos consecutivos
se deja vencer el watchdog; un éxito borra el contador de fallos.

El reinicio sucede al vencer el watchdog de 8 segundos desde su última
alimentación. Los motivos se imprimen en consola. Las comprobaciones reutilizan
la tarea de supervisión y solo mantienen una conexión local temporal; el consumo
real de memoria aún debe medirse en la placa. No comprueban acceso desde otra
computadora, gateway ni Internet. Con `WATCHDOG_ENABLED = False`, se registra
la falla y termina la supervisión, sin reinicio automático. Esta vigilancia
empieza después de conectar Ethernet y no cambia el límite del arranque inicial.

Para instalar este cambio, copiar **`main.py` y `config.py`** a la raíz de
la placa y reiniciar físicamente. La IP final sigue siendo `132.248.4.210`.
