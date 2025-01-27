from serial.tools import list_ports

ports = list_ports.comports()
for port in ports:
    print(f"Device: {port.device}, Description: {port.description}")
    print(f"VID:PID={port.vid}:{port.pid}")
