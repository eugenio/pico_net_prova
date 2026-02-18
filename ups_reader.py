"""Driver per UPS 52Pi EP-0159 via UART (GP0=TX, GP1=RX).

Legge tensione batteria e corrente dal modulo UPS.
Formato dati reale: tensione_mV|corrente_mA|campo3|campo4|\r
I messaggi possono essere duplicati e separati da byte spuri (0xC0, 0x84).
"""

from machine import UART, Pin


def init_ups():
    """Inizializza UART0 per comunicazione con il modulo UPS.

    Returns:
        UART: Oggetto UART configurato.
    """
    return UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))


def read_ups(uart):
    """Legge i dati dal modulo UPS.

    Args:
        uart: Oggetto UART inizializzato con init_ups().

    Returns:
        tuple: (voltage_V, current_mA) oppure None se nessun dato.
    """
    data = uart.readline()
    if data is None:
        return None
    try:
        # Rimuovi byte spuri e prendi il primo messaggio valido
        line = data.decode("utf-8", "ignore").strip()
        # Ogni messaggio finisce con | — split e prendi i primi campi
        parts = line.split("|")
        if len(parts) < 2:
            return None
        voltage_mv = float(parts[0])
        current_ma = float(parts[1])
        voltage_v = voltage_mv / 1000.0
        return (voltage_v, current_ma)
    except (ValueError, IndexError) as e:
        print(f"UPS parse error: {e}")
        return None
