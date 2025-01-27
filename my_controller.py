from arduino_device import ArduinoDevice, DeviceNotFoundError

class MyController:
    """
    High-level controller with default mappings:
      - SW1 -> 'mic switch' (optional)
      - SW2 -> 'cam switch' (optional)
      - LED1 -> 'mic LED'
      - LED2 -> 'cam LED'
      - POT -> volume or brightness (or both, or none)

    The user can selectively enable/disable these mappings via constructor flags.
    """

    def __init__(self,
                 enable_mic_switch=True,
                 enable_cam_switch=True,
                 enable_volume=True,
                 enable_brightness=True,
                 # For auto-detection, we pass the descriptor pattern
                 expected_pid=24577):
        """
        :param enable_mic_switch: If false, ignore sw1 for mic
        :param enable_cam_switch: If false, ignore sw2 for cam
        :param enable_volume:     If false, ignore volume mapping
        :param enable_brightness: If false, ignore brightness mapping
        :param expected_description: The hardware descriptor substring used by ArduinoDevice
        """
        self.enable_mic_switch = enable_mic_switch
        self.enable_cam_switch = enable_cam_switch
        self.enable_volume = enable_volume
        self.enable_brightness = enable_brightness

        # Create low-level device
        self.device = ArduinoDevice(expected_pid=expected_pid)

        # Event handlers
        self.on_mic_switch_changed = None
        self.on_cam_switch_changed = None
        self.on_volume_changed = None
        self.on_brightness_changed = None

        # We'll store last known volume/brightness if both are enabled
        self._last_volume = None
        self._last_brightness = None

        # Bind the device-level callbacks
        self.device.on_sw1_changed = self._handle_sw1_changed
        self.device.on_sw2_changed = self._handle_sw2_changed
        self.device.on_pot_changed = self._handle_pot_changed

    def connect(self):
        """
        If the device was not found during __init__, an exception was raised.
        Otherwise, just confirm the device is up.
        """
        # Device is already connected in ArduinoDevice.__init__()
        # But you could do additional checks or usage here if needed
        pass

    def disconnect(self):
        self.device.disconnect()

    # -----------------------
    #  LED Control
    # -----------------------
    def set_mic_led_active(self, active: bool):
        self.device.set_led1(active)

    def set_cam_led_active(self, active: bool):
        self.device.set_led2(active)

    def set_test_mode(self, enabled: bool):
        self.device.set_test_mode(enabled)

    # -----------------------
    #  Internal Switch Callbacks
    # -----------------------
    def _handle_sw1_changed(self, val: int):
        """
        SW1 => mic switch if enabled. 
        val is 0 if physically pressed, 1 if not pressed (inverted logic).
        """
        if self.enable_mic_switch and self.on_mic_switch_changed:
            self.on_mic_switch_changed(val)

    def _handle_sw2_changed(self, val: int):
        """
        SW2 => cam switch if enabled.
        """
        if self.enable_cam_switch and self.on_cam_switch_changed:
            self.on_cam_switch_changed(val)

    # -----------------------
    #  Internal Pot Handling
    # -----------------------
    def _handle_pot_changed(self, pot_value: int):
        """
        If both volume and brightness are enabled, 
        we can do a simple range-split (0..511 => volume, 512..1023 => brightness).
        If only volume or brightness is enabled, we do the entire 0..1023 range for that one.
        """
        if self.enable_volume and self.enable_brightness:
            # Split range
            if pot_value <= 511:
                new_volume = pot_value
                if new_volume != self._last_volume:
                    self._last_volume = new_volume
                    if self.on_volume_changed:
                        self.on_volume_changed(new_volume)
            else:
                new_brightness = pot_value - 512
                if new_brightness != self._last_brightness:
                    self._last_brightness = new_brightness
                    if self.on_brightness_changed:
                        self.on_brightness_changed(new_brightness)
        elif self.enable_volume and not self.enable_brightness:
            # entire 0..1023 range => volume
            if pot_value != self._last_volume:
                self._last_volume = pot_value
                if self.on_volume_changed:
                    self.on_volume_changed(pot_value)
        elif self.enable_brightness and not self.enable_volume:
            # entire 0..1023 range => brightness
            if pot_value != self._last_brightness:
                self._last_brightness = pot_value
                if self.on_brightness_changed:
                    self.on_brightness_changed(pot_value)
        else:
            # both volume & brightness are disabled => do nothing
            pass

if __name__ == '__main__':
    import time
    # Example usage
    controller = MyController()
    controller.connect()

    # Example event handlers
    def on_mic_switch(val):
        controller.set_mic_led_active(val)
        print(f"MIC switch: {'pressed' if val == 1 else 'released'}")

    def on_cam_switch(val):
        controller.set_cam_led_active(val)
        print(f"CAM switch: {'pressed' if val == 1 else 'released'}")

    def on_volume(vol):
        print(f"Volume: {vol}")

    def on_brightness(bright):
        print(f"Brightness: {bright}")

    # Bind the handlers
    controller.on_mic_switch_changed = on_mic_switch
    controller.on_cam_switch_changed = on_cam_switch
    controller.on_volume_changed = on_volume
    controller.on_brightness_changed = on_brightness

    # Run the controller
    try:
        while True:
            # Do nothing, just wait for events
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        controller.disconnect()
        print("Done.")