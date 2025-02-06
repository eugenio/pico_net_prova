import machine
import network
import os
from time import sleep
import binascii
import uos
from ucryptolib import aes
def add_or_update_network(wlan):

    # Scan for networks
    networks = wlan.scan()

    # Select the network to connect to
    print("Choose a network:")
    for i, network in enumerate(networks):
        print(f"{i}: {str(network).split("'")[1]}")

    choice = input("Input the number of the network you want to connect to: ")
    return str(networks[int(choice)]).split("'")[1]

def connect_to_network(network_name, wlan):    
    while True:
        network_password = input("Enter the password for " + network_name + ": ")
        if network_password == input("Confirm the password for " + network_name + ": "):
            break
        else:
            print("Passwords do not match. Please try again.")
    # Connect to the network

    wlan.connect(ssid=network_name, key=network_password)
    wlan.ipconfig(dhcp4=True)
    # Wait for the network to connect
    while not wlan.isconnected():
        print(f"Connecting to network {network_name}")
        print(f"Status: {wlan.status()}")
        sleep(1)
        pass
    # Print the IP address of the Raspberry Pi Pico W
    
    aes_param = setup_aes()
    encrypted_pw = encrypt_password(key=aes_param[0], iv=aes_param[1], MODE_CBC=aes_param[2], text_to_encrypt=network_password)   # Encrypt the password
    write_secrets(network_name, encrypted_pw)  # Write the encrypted password to a file

def read_secrets():
    # Read the network names and passwords from the file secrets.txt
    with open("secrets.txt") as f:
        secrets = f.read().splitlines()
        for secret in secrets:
            name, encrypted_password = secret.split(":")
            print(name)
            return encrypted_password


def write_secrets(network_name, encrypted_password):
    # Check if the file secrets.txt exists
    if not 'secrets.txt' in os.listdir("/"):
        # Write the encrypted password to a file
        f = open("/secrets.txt", 'w')
        f.write(network_name + ":" + str(encrypted_password))
        f.close()
    else:
        # Read the network names and passwords from the file secrets.txt
        f = open("/secrets.txt", 'r')
        secrets = f.read().splitlines()
        f.close()
        # Check if the network name is already in the file
        for secret in secrets:
            name, password = secret.split(":")
            if name == network_name:
                repl = input("Do you want to update the password for {network_name} network ? (Y/N) :")
                if repl == 'Y' or repl == 'y':
                    f = open("/secrets.txt", "w")
                    f.write(network_name + ":" + str(encrypted_password))
                    f.close()
                    break
                elif repl == 'N' or repl == 'n':
                    pass
                else:
                    pass
            else:
                pass



def connect_to_strongest_network(wlan):
    ssids = []
    # Scan for networks
    networks = wlan.scan()
    for i, network in enumerate(networks):
        ssids.append(str(network).split("'")[1])
    print(ssids)
    # Read the network names and passwords from the file secrets.txt
    f = open("secrets.txt", "r")
    secrets = f.read().splitlines()
    f.close()
    print(secrets)
    # For each network name and password, check if the network is available
    for secret in secrets:
        name, password = secret.split(":")
        if name in ssids:
            # Connect to the network with the strongest signal
            strongest_network = max(ssids, key=lambda network: network[3])
            if strongest_network[0] == name:
                wlan.connect(name, decypher_password(setup_aes(),password))
                while not wlan.isconnected():
                    print("Connecting to network " + name)
                    sleep(1)
                    pass
                print("Connected to network " + name)
                wlan.ipconfig("dhcp4")
def setup_aes():
    # AES key must be either 16, 24, or 32 bytes long
    key = b'[Secret Wokwi key with 256 bits]'# see how to use fuses to store the key in the device
    iv = uos.urandom(16)
    MODE_CBC = 2
    return [key, iv, MODE_CBC]

def encrypt_password(key, iv,MODE_CBC,text_to_encrypt):
    padded = text_to_encrypt + " " * (16 - len(text_to_encrypt) % 16)
    cipher = aes(key, MODE_CBC, iv)
    encrypted = cipher.encrypt(padded)
    return encrypted

def decypher_password(key, iv,MODE_CBC,encrypted):
    decipher = aes(key, MODE_CBC, iv)
    decrypted = decipher.decrypt(encrypted.encode('binary'))
    return decrypted.strip()


def main():
    # Initialize the network module
    # Set up the network interface
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while not wlan.isconnected() or not wlan.ifconfig("has_dhcp4"):
        try:
            # Connect to the strongest network
            connect_to_strongest_network(wlan)
            # Check if the Raspberry Pi Pico W is connected to a network
            if not 'secrets.txt' in os.listdir():
                net = add_or_update_network(wlan)
                print(net)
                connect_to_network(net, wlan)
                pass
            else:
                print("Connected to network: " + wlan.config("essid"))
                print("IP Address: " + wlan.ipconfig("addr4"))
                sleep(3)
        except KeyboardInterrupt:
            print("Exiting program")
            break

# Run the main function
main()
