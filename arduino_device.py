import serial
import time
import threading
from serial.tools import list_ports

class DeviceNotFoundError(Exception):
    """Raised when the specific Arduino device cannot be found."""
    pass

class ArduinoDevice:
    """
    Manages a serial connection to the Arduino.
    Auto-detects the correct port by looking for a specific hardware descriptor
    (e.g., 'Arduino UNO' or a particular VID:PID). Raises DeviceNotFoundError if not found.
    """

    def __init__(self, 
                 expected_pid=24577,  # Example description
                 baudrate=9600,
                 state_change_callback=None, 
                 timeout=1):
        """
        :param expected_description: A substring or exact match in port.description 
                                     to identify the correct device.
        :param baudrate: Serial baudrate
        :param timeout: Read timeout
        """
        self.baudrate = baudrate
        self.timeout = timeout
        self.expected_pid = expected_pid

        self.ser = None
        self.read_thread = None
        self.stop_flag = False

        self.invert_switches = False
 
        

        self.current_state = {
            "SW1": None,
            "SW2": None,
            "POT": None,
        }
        
        self.state_change_callback = state_change_callback

    def start(self):
        self.read_thread = threading.Thread(target=self._auto_detect_and_connect, daemon=True)
        self.read_thread.start()

    def _auto_detect_and_connect(self):
        """Enumerate serial ports; find the one matching `expected_description`; open it."""

        while not self.stop_flag:
            try:
                matching_port = None
                for p in list_ports.comports():
                    pid = p.pid or ""
                    if self.expected_pid == pid:
                        matching_port = p.device
                        break

                if not matching_port:
                    raise DeviceNotFoundError(
                        f"Could not find device with pid: '{self.pid}'."
                    )

                # We found our device, so open the serial port
                self.ser = serial.Serial(matching_port, self.baudrate, timeout=self.timeout)
                time.sleep(2)  # allow time for Arduino to reset on open

                # Start continuous background reading
                self.stop_flag = False
                print(f"Connected to Arduino on {matching_port}")
                self._read_loop() #blocks code
            except Exception as e:
                print(f"Error: {e}")
                print("Retrying in 1 seconds...")
                time.sleep(1)


    def disconnect(self):
        """Stop reading thread and close the serial port."""
        self.stop_flag = True
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()

    def request_sync(self):
        """Request an immediate snapshot of SW1, SW2, POT."""
        self.send_command("GET")

    def send_command(self, cmd: str):
        """Send a command string like 'LED1=1' to the Arduino."""
        if self.ser and self.ser.is_open:
            line = cmd.strip() + "\n"
            self.ser.write(line.encode("utf-8"))
        else:
            print(f"Serial port not open. Command '{cmd}' not sent.")

    # ------------------------------
    #  LED Control
    # ------------------------------
    def set_led(self, led_number, on_off):
        led_number = int(led_number)
        on_off = int(on_off)
        self.send_command(f"LED{led_number}={on_off}")

    def set_test_mode(self, enabled: bool):
        self.send_command("TEST=1" if enabled else "TEST=0")

    # ------------------------------
    #  Internal Reading
    # ------------------------------
    def _read_loop(self):

        if self.stop_flag:
            return
        # Run one time execution code here

        if not self.ser or not self.ser.is_open:
            return

        self.send_command("CONT=1")
        self.request_sync()

 
        while not self.stop_flag:

            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8").strip()
                    if line:
                        self._handle_line(line)
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                print(f"Serial error: {e}")
                break


    def _handle_line(self, line: str):
        """
        Possible lines (partial or multiple):
         - "SW1=0 SW2=1 POT=512"
         - "SW1=0"
         - "POT=300"
        We'll parse each token and dispatch callbacks.
        """
        parts = line.split()
        updates = {}
        for p in parts:
            if "=" in p:
                key, val_str = p.split("=", 1)
                updates[key] = val_str

        for key in updates:
            if key in self.current_state:
                if self.current_state[key] != int(updates[key]):
                    self.current_state[key] = int(updates[key])
                    if self.state_change_callback:
                        self.state_change_callback(updates)

def state_change_callback(state_changes_dict):
    print("State changes:", state_changes_dict)
    for key, value in state_changes_dict.items():
        if key == "SW1":
            print(f"SW1 changed to {value}")
            myDevice.set_led(1, value)
        elif key == "SW2":
            print(f"SW2 changed to {value}")
            myDevice.set_led(2, value)


if __name__ == "__main__":
    print("\nWelcome to Arduino CLI!")
    print("Attempting to connect to Arduino...\n")


    myDevice = ArduinoDevice(state_change_callback=state_change_callback)
    myDevice.start()

    while True:
        try:
            cmd = input("\nEnter command: ").strip().lower()
            parts = cmd.split()

            if not parts:
                continue

            command = parts[0]

            if command in ["exit", "quit", "q"]:
                print("Disconnecting...")
                myDevice.disconnect()
                print("Disconnected. Exiting.")
                break
            elif command in ["help", "h"]:
                print("\nAvailable commands:")
                print("  led <led_number> <on/off>   - Control LEDs")
                print("  test <on/off>               - Enable or disable test mode")
                print("  sync                        - Request sensor sync")
                print("  status                      - Show current sensor values")
                print("  exit                        - Disconnect and exit")
            elif command == "sync":
                myDevice.request_sync()
                print("Sync request sent.")
            elif command == "status":
                print("\nCurrent sensor values:")
                print(f"  SW1: {myDevice.current_state['SW1']}")
                print(f"  SW2: {myDevice.current_state['SW2']}")
                print(f"  POT: {myDevice.current_state['POT']}")
            elif command == "test" and len(parts) == 2:
                state = parts[1]
                if state in ["on", "off"]:
                    myDevice.set_test_mode(state == "on")
                    print(f"Test mode {'ENABLED' if state == 'on' else 'DISABLED'}")
                else:
                    print("Invalid test mode value. Use 'on' or 'off'.")
            elif command == "led" and len(parts) == 3:
                try:
                    led_number = int(parts[1])
                    state = parts[2]
                    if led_number in [1, 2] and state in ["on", "off"]:
                        myDevice.set_led(led_number, 1 if state=="on" else 0)
                        print(f"LED{led_number} turned {'ON' if state == 'on' else 'OFF'}")
                    else:
                        print("Invalid LED command. Use 'led <1/2> <on/off>'.")
                except ValueError:
                    print("Invalid LED number. Use 'led <1/2> <on/off>'.")
            else:
                print("Unknown command. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nDisconnecting...")
            myDevice.disconnect()
            print("Disconnected. Exiting.")
            break
        except Exception as e:
            print(f"Error: {e}")

