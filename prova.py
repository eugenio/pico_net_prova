import machine
import network
import os
from time import sleep
import ubinascii
import uos
from ucryptolib import aes
from micropython import const  # Needed for PKCS7 padding


def pad_pkcs7(data, block_size=16):
    padding_len = block_size - len(data) % block_size
    padding = bytes([padding_len] * padding_len)
    return data + padding

def unpad_pkcs7(data, block_size=16):
    padding_len = data[-1]
    if padding_len > block_size or padding_len < 1:
        raise ValueError("Invalid padding")
    return data[:-padding_len]

def encrypt_password(key, iv, MODE_CBC, text_to_encrypt):
    padded = pad_pkcs7(text_to_encrypt.encode())  # Encode to bytes
    cipher = aes(key, MODE_CBC, iv)
    encrypted = cipher.encrypt(padded)
    return ubinascii.hexlify(encrypted).decode()  # Store as hex string

def decypher_password(key, iv, MODE_CBC, encrypted):
    encrypted_bytes = ubinascii.unhexlify(encrypted) # Convert back from hex string
    decipher = aes(key, MODE_CBC, iv)
    decrypted_padded = decipher.decrypt(encrypted_bytes)
    decrypted = unpad_pkcs7(decrypted_padded).decode()  # Decode from bytes
    return decrypted

def add_or_update_network(wlan):

    # Scan for networks
    networks = wlan.scan()

    # Select the network to connect to
    print("Choose a network:")
    for i, network in enumerate(networks):
        print(f"{i}: {str(network).split("'")[1]}")

    choice = input("Input the number of the network you want to connect to: ")
    return str(networks[int(choice)]).split("'")[1]

def connect_to_network(network_name, wlan, aes_params):    
    while True:
        network_password = input("Enter the password for " + network_name + ": ")
        if network_password == input("Confirm the password for " + network_name + ": "):
            break
        else:
            print("Passwords do not match. Please try again.")
    # Connect to the network

    wlan.connect(ssid=network_name, key=network_password)
    wlan.ipconfig(dhcp4=True)  # Sets DHCP to True during connection

    # Wait for connection AND DHCP lease
    while not wlan.isconnected() or wlan.ifconfig()[0] is None: # Checks IP address to confirm connectivity
        print(f"Connecting to network {network_name}...")
        if wlan.status() < 0: # Check for errors
            print(f"Connection error: {wlan.status()}")
            break  # Exit the loop if there's a connection error
        sleep(1)

    if wlan.isconnected(): # Check connectivity *after* the loop to avoid printing incorrect info if connection failed.
        print("Connected to network: " + network_name)
        print(f"IP Address: {wlan.ifconfig()[0]}")
    
    encrypted_pw = encrypt_password(key=aes_params[0],
        iv=aes_params[1],
        MODE_CBC=aes_params[2],
        text_to_encrypt=network_password)
        # Encrypt the password
    write_secrets(network_name=network_name, encrypted_password=encrypted_pw, filename="secrets.txt")  # Write the encrypted password to a file

def read_secrets(filename="secrets.txt"):
    if filename in os.listdir("/"):
        # Read the network names and passwords from the file secrets.txt
        f = open(filename,'r')
        secrets = f.read().splitlines()
        for secret in secrets:
            print(secret)
            name, encrypted_password = secret.split(":")
            print(name, encrypted_password)
        f.close()
        return encrypted_password
    else:    
        print("File not found")
        return None
def write_secrets(network_name, encrypted_password=None, filename="secrets.txt"):
    # Check if the file secrets.txt exists
    if not filename in os.listdir("/"):
        # Write the encrypted password to a file
        f = open(filename, 'a')
        f.write(network_name + ":" + encrypted_password + "\n")
        f.close()
    else:
        # Read the network names and passwords from the file secrets.txt
        f = open(filename, 'r')
        secrets = f.read().splitlines()
        f.close()
        # Check if the network name is already in the file
        for secret in secrets:
            print(secret)
            name, password = secret.split(":")
            if name == network_name:
                repl = input(f"Do you want to update the password for {network_name} network ? (Y/N) :")
                if repl == 'Y' or repl == 'y':
                    f = open(filename, "w")
                    f.write(network_name + ":" + encrypted_password + "\n")
                    f.close()
                    break
                elif repl == 'N' or repl == 'n':
                    pass
                else:
                    pass
            else:
                pass

def connect_to_strongest_network(wlan, aes_params):
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
        try:
            name, password = secret.split(":")
            print(name, password)
            if name in ssids:
                print(f"Connecting to network {name}")
                decripted_password = decypher_password(aes_params[0], aes_params[1], aes_params[2], password)
                print(decripted_password)
                wlan.connect(name, decripted_password)
                wlan.ipconfig(dhcp4=True)  # Sets DHCP to True during connection

                # Wait for connection AND DHCP lease
                while not wlan.isconnected() or wlan.ifconfig()[0] is None: # Checks IP address to confirm connectivity
                    print(f"Connecting to network {name}...")
                    if wlan.status() < 0: # Check for errors
                        print(f"Connection error: {wlan.status()}")
                        break  # Exit the loop if there's a connection error
                    sleep(1)
        except UnicodeError as e:
            print("Unicode error: " + str(e))
            continue
        except Exception as e:
            print(f"Error connecting to network {name}: {str(e)}")
            continue

def get_signal_strength(networks):
    names_and_strengths = []
    for ap in networks:
        print(f'AP = {ap[0].decode()}, strength = {ap[3]}')
        names_and_strengths.append((ap[0].decode(), ap[3]))
    names_and_strengths = sorted(names_and_strengths)
    print(names_and_strengths)
    return names_and_strengths

def setup_aes():
    # AES key must be either 16, 24, or 32 bytes long
    key = b'[Secret Wokwi key with 256 bits]'# see how to use fuses to store the key in the device
    iv = uos.urandom(16)
    MODE_CBC = 2
    return [key, iv, MODE_CBC]

def main():
    # Initialize the network module
    # Set up the network interface
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Connect to the network

    while not wlan.isconnected() or not wlan.ifconfig()[0]:
        try:
            # Connect to the strongest network
            connect_to_strongest_network(wlan, aes_params)
            # Check if the Raspberry Pi Pico W is connected to a network
            if not 'secrets.txt' in os.listdir():
                net = add_or_update_network(wlan)
                print(net)
                connect_to_network(net, wlan, aes_params)
                pass
            else:
                print("Connected to network: " + wlan.config("essid"))
                print(f"IP Address: {wlan.ifconfig()[0]}")
                sleep(3)
        except KeyboardInterrupt:
            print("Exiting program")
            break
        except OSError as e:
            print("Error: " + str(e))
            net = add_or_update_network(wlan)
            connect_to_network(net, wlan, aes_params)
            pass

# Run the main function
def test_encryption(password, aes_params):
    encrypted = encrypt_password(aes_params[0], aes_params[1], aes_params[2], password)
    decrypted = decypher_password(aes_params[0], aes_params[1], aes_params[2], encrypted)
    print(f"Original: {password}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    
def test_pw_recovery_from_file(aes_params, password, filename="secrets.txt"):
    encrypted = read_secrets()
    decrypted = decypher_password(aes_params[0], aes_params[1], aes_params[2], encrypted)
    print(f"Original: {password}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")

def test_pw_saving_to_file(aes_params, password, network_name=None, filename="secrets.txt"):
    encrypted = encrypt_password(aes_params[0], aes_params[1], aes_params[2], password)
    write_secrets(network_name, filename=filename, encrypted_password=encrypted)
    print(f"Original: {password}")
    print(f"Encrypted: {encrypted}")

def test_recover_lines_from_file(aes_params, filename="secrets.txt"):
    encrypted = read_secrets()
    print(f"Encrypted: {encrypted}")
    decrypted = decypher_password(aes_params[0], aes_params[1], aes_params[2], encrypted)
    print(f"Decrypted: {decrypted}")
    
if __name__ == "__main__":
    aes_params = setup_aes()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    network_name = add_or_update_network(wlan)
    
    passwrd = input("Enter a password to test the encryption: ")
    
    try:
        test_recover_lines_from_file(aes_params)
    except Exception as e:
        print(f"Error: {str(e)}")
        pass
    test_encryption(passwrd, aes_params)  # Test with a known password
    test_pw_saving_to_file(aes_params, passwrd, network_name=network_name, filename="secrets.txt")
    print(f"Files in directory / : {os.listdir('/')}")
    test_pw_recovery_from_file(aes_params, passwrd)
    main() # Call main() afterwards if the test passes
