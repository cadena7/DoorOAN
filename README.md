# DoorOAN — MicroPython / Olimex ESP32-EVB

Adaptación de `Python/DoorOAN/dooroan.py` (Flask y BeagleBone Black).
Conserva inicio/cierre de sesión, estado de puerta, pulso de 4 segundos,
una única página con cámara de puerta, botón de mando y alarma sonora.
La interfaz se reconstruyó sin Jinja, jQuery, fuentes ni archivos pesados.
La cámara de puerta conserva la dirección original; el navegador la consulta
directamente y necesita acceso a la red OAN. Su disponibilidad no se comprobó.

## Conexiones

| Función | GPIO | Conexión |
| --- | --- | --- |
| Pulso de apertura/cierre | 32 | REL1 integrado, activo alto; usar COM y NO como contacto seco del controlador |
| Relé sin uso | 33 | REL2 integrado, siempre apagado |
| Estado de puerta | 4 | Entrada UEXT TX desde OUT del optoacoplador, con pull-down interno; ver `conexiones.md` |

GPIO4 se configura como entrada con pull-down interno (`SENSOR_PULL = "down"`).
Esta configuración corresponde a salida activa alta; para colector abierto
que conduce a GND, verificar si debe usarse `SENSOR_PULL = "up"` y ajustar
`SENSOR_CLOSED_LEVEL`. El switch Eaton NO de estado cierra cuando se abre
la puerta. Sin activar, con contacto abierto, se interpreta puerta cerrada.
`SENSOR_CLOSED_LEVEL` debe ser el nivel medido en OUT cuando el switch está
sin activar: 0 para bajo, 1 para alto. El valor actual es 0 y requiere
comprobarlo en el módulo real. Un cable de estado cortado puede producir
la misma lectura que puerta cerrada con esta configuración NO.
No conectar 5 V ni la alimentación del motor a GPIO4. Reservar UEXT TX para
el sensor: no usar UART1 simultáneamente. REL1 debe accionar la entrada del
controlador de puerta, no alimentar directamente el motor.

La asignación se basa en el [esquema oficial Olimex revisión K1](https://github.com/OLIMEX/ESP32-EVB/blob/master/HARDWARE/REV-K1/ESP32-EVB_Rev_K1.sch).
Comprobar la revisión impresa de tu placa antes de cablear. Se utiliza
Ethernet integrado con IP estática; CAN y microSD no se inicializan.

## Instalación

1. Instalar firmware MicroPython para ESP32 clásico con soporte `network.LAN`
   (ESP32-EVB, no ESP32-S3/C3).
2. Editar `config.py`: comprobar valores `ETH_*`, `USERNAME` y `PASSWORD`.
   `LOGIN_REQUIRED = False` por defecto: no pide login. Con `True`, configurar
   usuario y contraseña; se permite `admin / admin` (valores por defecto).
   Solo la contraseña vacía impide arrancar cuando el login está habilitado.
3. Copiar `config.py`, `hardware.py`, `webapp.py` y `main.py` a la raíz del
   sistema de archivos de la placa. Copiar la carpeta `lib` completa;
   incluye el Microdot ya presente en este proyecto.
4. Conectar RJ45 a la red OAN y reiniciar. La consola serie muestra
   `http://132.248.4.210`.
5. Abrir la página (iniciar sesión solo si `LOGIN_REQUIRED = True`) y probar
   el pulso primero sin conectar el controlador.
   Confirmar que REL1 vuelve a apagarse después de cuatro segundos, que
   REL2 no se activa y que el contacto del sensor cambia el estado mostrado.

Puedes transferir estos archivos con Thonny o, con mpremote instalado:

```powershell
mpremote connect COM5 fs cp config.py :config.py
mpremote connect COM5 fs cp hardware.py :hardware.py
mpremote connect COM5 fs cp webapp.py :webapp.py
mpremote connect COM5 fs cp main.py :main.py
mpremote connect COM5 fs cp -r lib :
mpremote connect COM5 reset
```

Sustituir COM5 por el puerto real. No copiar pruebas ni README a la placa.

## Ethernet estático

Valores recuperados de `Python/DoorOAN/Instalacion/network/interfaces`, eth0:

| Parámetro | Valor |
| --- | --- |
| IP | 132.248.4.210 |
| Máscara | 255.255.255.0 |
| Gateway | 132.248.4.254 |
| DNS | 8.8.8.8 |

Desconectar la BeagleBone al sustituirla: no utilizar la misma IP en ambos
equipos simultáneamente. No se usa la IP USB 192.168.7.2 del archivo original.
Microdot escucha directamente en el puerto HTTP 80: abrir
`http://132.248.4.210` sin especificar puerto. Esta placa no ejecuta nginx.

Se configura el PHY LAN8710A integrado (dirección 0), MDC GPIO23, MDIO GPIO18,
y reloj externo RMII de entrada en GPIO0, sin power GPIO. El constructor usa
`ref_clk`/`ref_clk_mode`; contempla la API antigua `clock_mode` si no admite
esos argumentos. GPIO4 del sensor y GPIO32 de REL1 no interfieren con Ethernet.
Si no hay enlace en 30 segundos, muestra error y apaga la interfaz; revisar
cable/switch y reiniciar. Validar el enlace en la placa real y comprobar su
revisión contra el esquema Olimex.

## Comportamiento

- `/` y `/index.html`: acceso, control, webcam y estado actualizado cada 1.5 s.
- `/api/status`: JSON con `estado` y `activando`; lectura con comprobación de
  estabilidad de 80 ms (una transición puede aparecer como `inestable`).
- `/loginuser`: con login habilitado, GET redirige y POST inicia sesión;
  con login deshabilitado, redirige a la página principal.
- `/logoutuser` y `/openclose`: solo POST. El formulario de mando siempre
  incluye token CSRF; la sesión se exige solo si `LOGIN_REQUIRED = True`.
- La alarma está habilitada por defecto; se silencia en «Opciones de sonido»
  al pie. El navegador puede requerir un primer toque para desbloquear audio.
  Se genera localmente, sin MP3, y recuerda la preferencia en ese navegador.
- Pulso asíncrono: otras consultas siguen funcionando. Las solicitudes de
  mando esperan su turno y ejecutan un pulso cada una, sin solaparse. Entre
  pulsos REL1 queda apagado durante `PULSE_GAP_MS` (100 ms por defecto).
  Temporizador y bloque `finally` apagan REL1. El botón se deshabilita al
  enviar para evitar clics repetidos desde la misma página; otras solicitudes
  esperan en el servidor. Se admite un mando activo y dos esperando; los
  adicionales reciben HTTP 503 y no se ejecutan.
- Sesiones aleatorias en RAM: duran una hora, máximo cuatro y se eliminan
  al reiniciar. Cookies HttpOnly y SameSite=Strict.
- Si falla la configuración/red, el relé permanece apagado y se muestra
  el error en consola. Tras corregirlo, reiniciar.

El servidor usa HTTP: utilizarlo dentro de una red de confianza. El temporizador
no sustituye las protecciones eléctricas del controlador frente a un bloqueo
total del microcontrolador. El firmware y el cableado requieren verificación
en la placa real.

Referencia de APIs: [MicroPython ESP32](https://docs.micropython.org/en/latest/esp32/quickref.html).

## Documentación y actualización

Watchdog y límites HTTP: consultar la sección «Protección del servidor» de
`sube.md`. Subir `main.py`, `config.py`, `webapp.py` y la biblioteca Microdot
local actualizada. Los límites se ajustan en `config.py`.

- `sube.md`: archivos que se cargan al ESP32, pasos de instalación y alarma sonora.
- `conexiones.md` y `conexiones.png`: cableado de REL1 y switch NO mediante opto.
- Para actualizar una instalación anterior a Ethernet, puerto 80 y GPIO4,
  copiar `main.py`, `config.py` y `hardware.py`, conservando las credenciales
  locales en `config.py`, y reiniciar la placa.
- Para incorporar login opcional y mandos en espera, copiar también `webapp.py`.
  Con el login deshabilitado, cualquier persona con acceso a la página puede
  accionar el botón; el token del formulario no es una contraseña.
