from arduino_device import ArduinoDevice, DeviceNotFoundError

class MyController:


    def __init__(self, state_change_callback=None):

        # Create low-level device
        self.state_change_callback = state_change_callback
        self.device = ArduinoDevice(state_change_callback=self._internal_state_change_callback)
        self.device.start()

        self.mapping = {
            "SW1": "mic",
            "SW2": "cam",
            "POT": "vol",
        }

        self.reverse_switch_mapping = {v: k for k, v in self.mapping.items() if k.startswith("SW")}

        #for debugging

        print(f"reverse_mapping: {self.reverse_switch_mapping}")

    def _internal_state_change_callback(self, state_dictionary):

        up_dict = {}

        for key, value in state_dictionary.items():
            if key in self.mapping:
                up_dict[self.mapping[key]] = value

        if self.state_change_callback:
            self.state_change_callback(up_dict)

    def led(self, led, value):
        if led in self.reverse_switch_mapping:
            led 
            led_number = int(self.reverse_switch_mapping[led].split("SW")[1])
            self.device.set_led(led_number, value)
        else:
            print("LED not found")


    def stop(self):
        self.device.disconnect()


if __name__ == '__main__':


    def on_state_change_callback(state_changes_dict):
        print("State changes:", state_changes_dict)


    controller = MyController(state_change_callback=on_state_change_callback)

    while True:
        try:
            cmd = input("\nEnter command: ").strip().lower()
            parts = cmd.split()

            if not parts:
                continue

            command = parts[0]

            if command in ["exit", "quit", "q"]:
                print("Disconnecting...")
                controller.stop()
                print("Disconnected. Exiting.")
                break
            elif command in ["help", "h"]:
                print("\nAvailable commands:")
                print("  led <led_name> <on/off>     - Control LEDs")
                print("  exit                        - Disconnect and exit")

            elif command == "led" and len(parts) == 3:
                try:
                    led_name = parts[1]
                    state = parts[2]
                    if  state in ["on", "off"]:
                        controller.led(led_name, 1 if state == "on" else 0)
                        print(f"LED for {led_name} turned {state}")
                    else:
                        print("Invalid LED command. Use 'led <1/2> <on/off>'.")
                except ValueError:
                    print("Invalid LED number. Use 'led <1/2> <on/off>'.")
            else:
                print("Unknown command. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nDisconnecting...")
            controller.stop()
            print("Disconnected. Exiting.")
            break
        except Exception as e:
            print(f"Error: {e}")
