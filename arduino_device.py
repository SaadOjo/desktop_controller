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

        # Store current states (inverted switch logic: 0=pressed, 1=not pressed)
        self.sw1 = None
        self.sw2 = None
        self.pot = None

        # Callbacks for changes
        self.on_sw1_changed = None  # function(int new_val)
        self.on_sw2_changed = None  # function(int new_val)
        self.on_pot_changed = None  # function(int new_val)

        # Attempt to find and open the device
        self._auto_detect_and_connect()

    def _auto_detect_and_connect(self):
        """Enumerate serial ports; find the one matching `expected_description`; open it."""
        matching_port = None
        for p in list_ports.comports():
            # Check if the device description contains our expected string
            # or if p.vid / p.pid match known vendor/product IDs.
            # Example: p.description might be "Arduino UNO (COM3)" on Windows
            # or "/dev/ttyACM0 - Arduino Uno" on Linux, etc.
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
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        # Enable continuous transmit mode and request an initial sync
        self.send_command("CONT=1")
        self.request_sync()

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

    # ------------------------------
    #  LED Control
    # ------------------------------
    def set_led1(self, on_off: bool):
        self.send_command("LED1=1" if on_off else "LED1=0")

    def set_led2(self, on_off: bool):
        self.send_command("LED2=1" if on_off else "LED2=0")

    def set_test_mode(self, enabled: bool):
        self.send_command("TEST=1" if enabled else "TEST=0")

    # ------------------------------
    #  Internal Reading
    # ------------------------------
    def _read_loop(self):
        while not self.stop_flag:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8").strip()
                    if line:
                        self._handle_line(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                # In production, handle/log errors more robustly
                print(f"[ArduinoDevice] Serial read error: {e}")
                time.sleep(0.5)

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

        if "SW1" in updates:
            new_sw1 = int(updates["SW1"])
            if self.sw1 != new_sw1:
                self.sw1 = new_sw1
                if self.on_sw1_changed:
                    self.on_sw1_changed(new_sw1)

        if "SW2" in updates:
            new_sw2 = int(updates["SW2"])
            if self.sw2 != new_sw2:
                self.sw2 = new_sw2
                if self.on_sw2_changed:
                    self.on_sw2_changed(new_sw2)

        if "POT" in updates:
            new_pot = int(updates["POT"])
            if self.pot != new_pot:
                self.pot = new_pot
                if self.on_pot_changed:
                    self.on_pot_changed(new_pot)
