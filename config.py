"""Configuración local; editar antes de cargar a la placa."""
# Red estática tomada de Python/DoorOAN/Instalacion/network/interfaces (eth0).
ETH_IP = "132.248.4.210"
ETH_NETMASK = "255.255.255.0"
ETH_GATEWAY = "132.248.4.254"
ETH_DNS = "8.8.8.8"
# ESP32-EVB: LAN8710A, reloj externo RMII en GPIO0, sin power GPIO.
ETH_PHY_ADDR = 0
ETH_MDC_GPIO = 23
ETH_MDIO_GPIO = 18
ETH_REF_CLK_GPIO = 0
NETWORK_TIMEOUT_S = 30
HTTP_PORT = 80
HTTP_MAX_CONNECTIONS = 6
HTTP_REQUEST_TIMEOUT_S = 5
HTTP_HANDLER_TIMEOUT_S = 15
HTTP_RESPONSE_TIMEOUT_S = 5
HTTP_CLOSE_TIMEOUT_S = 1
MAX_PENDING_COMMANDS = 2
WATCHDOG_ENABLED = True
WATCHDOG_TIMEOUT_MS = 8000
WATCHDOG_FEED_MS = 1000
USERNAME = "admin"
LOGIN_REQUIRED = False  # True exige login; False muestra el botón directamente.
PASSWORD = "admin"  # Se permite admin/admin cuando LOGIN_REQUIRED es True.
PULSE_GAP_MS = 100  # Pausa con REL1 apagado entre instrucciones.
RELAY_GPIO = 32  # REL1 integrado, activo alto.
UNUSED_RELAY_GPIO = 33  # REL2 se mantiene apagado.
SENSOR_GPIO = 4  # UEXT TX: reservar para OUT del opto, sin UART1.
SENSOR_PULL = "down"  # Salida activa alta; usar "up" si el módulo exige pull-up.
SENSOR_CLOSED_LEVEL = 0  # Nivel OUT con switch NO sin activar (puerta cerrada).
# Verificar módulo: si OUT es alto con switch sin activar, cambiar a 1.
PULSE_MS = 4000
DEBOUNCE_MS = 80
SESSION_SECONDS = 3600
MAX_SESSIONS = 4
DOOR_CAMERA = "http://132.248.4.207/cgi-bin/viewer/video.jpg"
