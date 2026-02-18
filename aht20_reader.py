"""Driver per Grove AHT20 I2C su Pico W (GP4=SDA, GP5=SCL).

Legge temperatura e umidità senza librerie esterne.
"""

from machine import Pin, I2C
import utime

AHT20_ADDR = 0x38
CMD_INIT = bytes([0xBE, 0x08, 0x00])
CMD_MEASURE = bytes([0xAC, 0x33, 0x00])
CMD_RESET = bytes([0xBA])


def init_aht20(i2c):
    """Inizializza e calibra il sensore AHT20."""
    i2c.writeto(AHT20_ADDR, CMD_INIT)
    utime.sleep_ms(40)
    status = i2c.readfrom(AHT20_ADDR, 1)[0]
    if not status & 0x08:
        raise RuntimeError("AHT20: calibrazione fallita")


def read_aht20(i2c):
    """Legge temperatura (°C) e umidità (% RH) dal sensore.

    Returns:
        tuple: (temperatura, umidità)
    """
    i2c.writeto(AHT20_ADDR, CMD_MEASURE)
    utime.sleep_ms(80)

    data = i2c.readfrom(AHT20_ADDR, 7)

    # Attendi che il sensore non sia più busy
    while data[0] & 0x80:
        utime.sleep_ms(10)
        data = i2c.readfrom(AHT20_ADDR, 7)

    hum_raw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
    temp_raw = ((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]

    humidity = (hum_raw / 1048576) * 100  # 2^20 = 1048576
    temperature = (temp_raw / 1048576) * 200 - 50

    return temperature, humidity


def main():
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400_000)

    devices = i2c.scan()
    print(f"Dispositivi I2C: {[hex(d) for d in devices]}")

    if AHT20_ADDR not in devices:
        print("ERRORE: AHT20 non trovato su 0x38")
        return

    init_aht20(i2c)
    print("AHT20 inizializzato\n")

    while True:
        try:
            temp, hum = read_aht20(i2c)
            print(f"Temp: {temp:.1f}°C  Umidità: {hum:.1f}%")
        except OSError as e:
            print(f"Errore I2C: {e}")
        utime.sleep(2)


if __name__ == "__main__":
    main()
