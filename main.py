import machine
import network
import time
import ujson
import webrepl
from machine import Pin, I2C
from time import sleep
from umqtt.simple import MQTTClient

from aht20_reader import init_aht20, read_aht20
from ups_reader import init_ups, read_ups
from mqtt_config import (
    WIFI_SSID, WIFI_PASSWORD,
    MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    MQTT_CLIENT_ID, PUBLISH_INTERVAL, WEBREPL_PASSWORD,
)

# --- MQTT topics ---
STATE_TOPIC = "pico_w/aht20/state"
DISCOVERY_TEMP = "homeassistant/sensor/pico_w_aht20/temperature/config"
DISCOVERY_HUM = "homeassistant/sensor/pico_w_aht20/humidity/config"
DISCOVERY_BATT_V = "homeassistant/sensor/pico_w_aht20/battery_voltage/config"
DISCOVERY_BATT_I = "homeassistant/sensor/pico_w_aht20/battery_current/config"


def connect_to_network_stub(network_name, wlan, network_password, timeout=20):
    try:
        wlan.connect(ssid=network_name, key=network_password)
    except Exception as e:
        print(f"WiFi connect error: {e}")
        return
    try:
        wlan.ipconfig(dhcp4=True)
    except Exception as e:
        print(f"DHCP error: {e}")
    for i in range(timeout):
        try:
            if wlan.isconnected() and wlan.ifconfig()[0] is not None:
                break
        except Exception:
            pass
        print(f"Connecting to {network_name}... ({i+1}/{timeout})")
        if wlan.status() < 0:
            print(f"Connection error: {wlan.status()}")
            break
        sleep(1)
    if wlan.isconnected():
        print("Connected to network: " + network_name)
        print(f"IP Address: {wlan.ifconfig()[0]}")
    else:
        print(f"WiFi timeout dopo {timeout}s")


# --- MQTT ---

def mqtt_connect():
    """Connette al broker MQTT e ritorna il client."""
    client = MQTTClient(
        MQTT_CLIENT_ID,
        MQTT_BROKER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=60,
    )
    client.connect()
    return client


def _build_discovery_config(name, unit, template, dev_class, uid):
    """Costruisce un singolo payload discovery JSON come stringa."""
    return (
        '{"name":"' + name + '",'
        '"state_topic":"' + STATE_TOPIC + '",'
        '"unit_of_measurement":"' + unit + '",'
        '"value_template":"{{ value_json.' + template + ' }}",'
        '"device_class":"' + dev_class + '",'
        '"state_class":"measurement",'
        '"unique_id":"' + uid + '",'
        '"device":{"identifiers":["pico_w_aht20"],'
        '"name":"Pico W AHT20",'
        '"manufacturer":"Raspberry Pi",'
        '"model":"Pico W"}}'
    )


def _build_discovery_configs():
    """Costruisce la lista di (topic, payload) per il discovery HA."""
    return [
        (DISCOVERY_TEMP, _build_discovery_config(
            "Pico W Temperatura", "C", "temperature", "temperature", "pico_w_aht20_temp")),
        (DISCOVERY_HUM, _build_discovery_config(
            "Pico W Umidita", "%", "humidity", "humidity", "pico_w_aht20_hum")),
        (DISCOVERY_BATT_V, _build_discovery_config(
            "Pico W Batt Tensione", "V", "battery_voltage", "voltage", "pico_w_aht20_batt_v")),
        (DISCOVERY_BATT_I, _build_discovery_config(
            "Pico W Batt Corrente", "mA", "battery_current", "current", "pico_w_aht20_batt_i")),
    ]


def publish_once(led, i2c, aht20_ok, ups_uart):
    """Legge sensori e pubblica MQTT una volta."""
    import gc
    gc.collect()

    # Lettura sensori
    temp, hum = None, None
    if aht20_ok:
        try:
            temp, hum = read_aht20(i2c)
            print(f"Temp: {temp:.1f}C  Umidita: {hum:.1f}%")
        except OSError as e:
            print(f"Errore lettura sensore: {e}")

    ups_data = read_ups(ups_uart)
    if ups_data:
        print(f"UPS: {ups_data[0]:.2f}V  {ups_data[1]:.1f}mA")
    else:
        print("UPS: nessun dato")

    # Publish MQTT
    if temp is not None:
        try:
            client = mqtt_connect()
            data = {
                "temperature": round(temp, 1),
                "humidity": round(hum, 1),
            }
            if ups_data:
                data["battery_voltage"] = round(ups_data[0], 2)
                data["battery_current"] = round(ups_data[1], 1)
            payload = ujson.dumps(data)
            led.on()
            client.publish(STATE_TOPIC, payload)
            sleep(0.3)
            led.off()
            sleep(0.2)
            led.on()
            sleep(0.3)
            led.off()
            client.disconnect()
            print(f"MQTT pubblicato: {payload}")
        except Exception as e:
            print(f"Errore MQTT: {e}")
            led.off()


# --- Main ---

def main():
    import gc
    gc.collect()

    network.country('FR')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0xa11140)  # Disabilita power-saving
    gc.collect()

    # LED onboard (richiede CYW43 attivo)
    led = machine.Pin("LED", machine.Pin.OUT)

    # Blink di avvio
    led.on()
    sleep(2)
    led.off()

    # 1. Connessione WiFi
    connect_to_network_stub(WIFI_SSID, wlan, WIFI_PASSWORD)

    if not wlan.isconnected():
        print("WiFi non connesso, retry in 30s")
        for _ in range(3):
            led.on(); sleep(0.1); led.off(); sleep(0.1)
        sleep(30)
        machine.reset()

    # 1b. Avvia WebREPL
    webrepl.start(password=WEBREPL_PASSWORD)
    print(f"WebREPL attivo su ws://{wlan.ifconfig()[0]}:8266")

    # 2. Init sensore AHT20
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400_000)
    devices = i2c.scan()
    print(f"Dispositivi I2C: {[hex(d) for d in devices]}")

    aht20_ok = False
    if 0x38 in devices:
        try:
            init_aht20(i2c)
            aht20_ok = True
            print("AHT20 inizializzato")
        except Exception as e:
            print(f"AHT20 init fallito: {e}")
    else:
        print("AHT20 non trovato, continuo senza sensore")

    # 2b. Init UPS
    ups_uart = init_ups()
    print("UPS UART inizializzata")
    time.sleep(1)

    # 3. Discovery MQTT (una volta al boot)
    discovery_configs = _build_discovery_configs()
    for topic, payload in discovery_configs:
        try:
            client = mqtt_connect()
            client.publish(topic, payload, retain=True)
            client.disconnect()
        except Exception as e:
            print(f"Discovery error ({topic}): {e}")
        time.sleep(0.5)
    print(f"Discovery pubblicato ({len(discovery_configs)} entita)")

    # 4. Primo publish immediato
    publish_once(led, i2c, aht20_ok, ups_uart)

    # 5. Loop con soft sleep — WebREPL resta attivo
    print(f"Loop publish ogni {PUBLISH_INTERVAL}s")
    while True:
        time.sleep(PUBLISH_INTERVAL)
        publish_once(led, i2c, aht20_ok, ups_uart)


if __name__ == "__main__":
    main()
