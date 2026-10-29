"""Configuración local; editar antes de cargar a la placa."""
# Seleccionar "lab" para pruebas locales o "final" para la implementación.
NETWORK_PROFILE = "final"
# Tuplas: IP, máscara, gateway y DNS. Ajustar gateway si el router usa otra IP.
NETWORK_PROFILES = {
    "lab": ("192.168.0.210", "255.255.255.0", "192.168.0.1", "8.8.8.8"),
    # Red original de Python/DoorOAN/Instalacion/network/interfaces (eth0).
    "final": ("132.248.4.210", "255.255.255.0", "132.248.4.254", "8.8.8.8"),
}
ETH_IP, ETH_NETMASK, ETH_GATEWAY, ETH_DNS = NETWORK_PROFILES[NETWORK_PROFILE]
# ESP32-EVB: LAN8710A, reloj externo RMII en GPIO0, sin power GPIO.
ETH_PHY_ADDR = 0
ETH_MDC_GPIO = 23
ETH_MDIO_GPIO = 18
ETH_REF_CLK_GPIO = 0
NETWORK_TIMEOUT_S = 30
HTTP_PORT = 80
HTTP_MAX_CONNECTIONS = 6
HTTP_REQUEST_TIMEOUT_S = 5
HTTP_HANDLER_TIMEOUT_S = 30
HTTP_RESPONSE_TIMEOUT_S = 5
HTTP_CLOSE_TIMEOUT_S = 1
MAX_PENDING_COMMANDS = 2
WATCHDOG_ENABLED = True
WATCHDOG_TIMEOUT_MS = 8000
WATCHDOG_FEED_MS = 1000
ETH_LINK_TIMEOUT_S = 30  # Corte continuo antes de dejar vencer el watchdog.
HTTP_HEALTH_INTERVAL_S = 15
HTTP_HEALTH_TIMEOUT_S = 2
HTTP_HEALTH_FAILURES = 3  # Fallos consecutivos; un éxito borra el contador.
USERNAME = "admin"
LOGIN_REQUIRED = False  # True exige login; False muestra el botón directamente.
PASSWORD = "admin"  # Se permite admin/admin cuando LOGIN_REQUIRED es True.
RELAY_GPIO = 32  # REL1 integrado, activo alto.
UNUSED_RELAY_GPIO = 33  # REL2 se mantiene apagado.
SENSOR_GPIO = 17  # EXT1: GPIO17/SPI_CS; reservado para OUT, sin SPI en UEXT.
SENSOR_PULL = "up"  # OUT activo bajo: 3.2 V sin activar, 0.10 V con opto activo.
SENSOR_CLOSED_LEVEL = 1  # Switch NO sin activar: OUT alto, puerta cerrada.
PULSE_MS = 4000
PULSE_GAP_MS = PULSE_MS  # Pausa apagado igual a la duración del pulso.
DEBOUNCE_MS = 80
SESSION_SECONDS = 3600
MAX_SESSIONS = 4
DOOR_CAMERA = "http://132.248.4.207/cgi-bin/viewer/video.jpg"
