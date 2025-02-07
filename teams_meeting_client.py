import os
import json
import threading
import asyncio
import websockets
from typing import Callable, Optional
from urllib.parse import quote
from datetime import datetime
from rich import print as pprint
from pprint import pprint as ppp
#from rich.pretty import pprint
from colorama import Fore, Back, Style


DEFAULT_TOKEN = "61e9d3d4-dbd6-425d-b80f-8110f48f769c"
TOKEN_FILE = "token.txt"

class TeamsMeetingClient:
    def __init__(
        self,
        manufacturer: str = "Token Financial Technologies",
        device: str = "ortaboy",
        app: str = "ortanator",
        app_version: str = "1.0.00",
        state_change_callback: Optional[Callable[[dict], None]] = None
    ):
        """
        :param manufacturer: Defaults to "YourManufacturer"
        :param device: Defaults to "YourDevice"
        :param app: Defaults to "YourApp"
        :param app_version: Defaults to "2.0.26"
        :param meeting_started_callback: Function called when a meeting starts
        :param meeting_ended_callback: Function called when a meeting ends
        """
        self.manufacturer = manufacturer
        self.device = device
        self.app = app
        self.app_version = app_version
        self.state_change_callback = state_change_callback
        self.ws = None

        self.current_state = { #None means do not know
            "isInMeeting": None,
            "isMuted": None,
            "isVideoOn": None,
            "isBackgroundBlurred": None,
            "isHandRaised": None,
            "isRecordingOn": None,
            "isSharing": None,
            "hasUnreadMessages": None,
            "isWsConnected": None
        }

        # Load token from file if available, else use default
        self.token = self._load_token()
        
        # For sending commands with incrementing request IDs
        self.request_id_counter = 1

        # WebSocket connection details
        self.ws_url = (
            f"ws://localhost:8124"
            f"?token={self.token}"
            f"&protocol-version=2.0.0"
            f"&manufacturer={quote(self.manufacturer)}"
            f"&device={quote(self.device)}"
            f"&app={quote(self.app)}"
            f"&app-version={self.app_version}"
        )

        # Thread control
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)

    def start(self):
        """Start the background thread to connect and listen to the WebSocket."""
        self.thread.start()

    def stop(self):
        """Stop the WebSocket connection and background thread."""
        self.stop_event.set()
        # Attempt to close the websocket by connecting to the event loop
        try:
            # We send a dummy command to wake up the loop if needed
            asyncio.run_coroutine_threadsafe(self._close_ws(), self.loop)
        except Exception:
            pass
        self.thread.join()

    def get_full_state(self) -> dict:
        """Return the full state of the client."""
        return self.current_state

    def send_custom_command(self, action: str, parameters: dict):
        """Send a custom command to the WebSocket server."""
        action_data = {
            "action": action,
            "parameters": parameters,
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def send_pairing_request(self):
        """Send a pairing request to the WebSocket server."""
        action_data = {
            "action": "pair",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def send_reaction(self, reaction_type: str):
        """Send a reaction command (e.g., like, love, applause, wow, laugh)."""
        action_data = {
            "action": "send-reaction",
            "parameters": {"type": reaction_type},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def toggle_background_blur(self):
        action_data = {
            "action": "toggle-background-blur",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def toggle_video(self):
        action_data = {
            "action": "toggle-video",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def set_camera(self, value):
        print("calling set camera")
        value = bool(int(value))
        if value != bool(self.current_state["isVideoOn"]):
            print(f"toggle_video: {value}")
            self.toggle_video()


    def toggle_mute(self):
        action_data = {
            "action": "toggle-mute",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)


    def set_microphone(self, value):
        print(f"calling set microphone")
        value = not bool(int(value))
        if value != bool(self.current_state["isMuted"]):
            print(f"toggle_mute: {value}")
            self.toggle_mute()

    def toggle_hand(self):
        action_data = {
            "action": "toggle-hand",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    def leave_call(self):
        action_data = {
            "action": "leave-call",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

    # --------------------------------------------------------
    # Internals
    # --------------------------------------------------------

    def _uninitialize_current_state(self):
        for key in self.current_state:
            self.current_state[key] = None

    def _get_current_time_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    def _log_message_send(self, message):
        pprint(f"\n[bold red][{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nSENT: {message} [/bold red]")

    def _log_message_received(self, message):
        pprint(f"\n[bold green][{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nRECEIVED: {json.loads(message)} [/bold green]")
    def _get_request_id(self) -> int:
        return 1

    def _load_token(self) -> str:
        """Load token from file if it exists, else return DEFAULT_TOKEN."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                return f.read().strip()
        return DEFAULT_TOKEN

    def _save_token(self, new_token: str):
        """Save the new token to file."""
        with open(TOKEN_FILE, "w") as f:
            f.write(new_token)

    def _run_event_loop(self):
        """Run an asyncio event loop in a background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_and_listen())

    async def _connect_and_listen(self):
        while not self.stop_event.is_set():
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    print(f"Connected to {self.ws_url}")
                    self.current_state["isWsConnected"] = True
                    if self.state_change_callback:
                        self.state_change_callback({"isWsConnected": True})
                    # Listen for messages until the connection is closed or stop_event is set.
                    await self._receive_loop(ws)
            except websockets.ConnectionClosed:
                print("WebSocket connection closed. Attempting to reconnect...")
            except Exception as e:
                print(f"WebSocket connection failed: {e}")
            finally:
                # Whether an error occurred or the connection closed, mark as disconnected.
                self.current_state["isWsConnected"] = False
                self.ws = None
                if self.state_change_callback:
                    self.state_change_callback({"isWsConnected": False})
                
            # If the stop_event is not set, wait a few seconds before reconnecting.
            if not self.stop_event.is_set():
                print("Waiting 3 seconds before attempting to reconnect...")
                await asyncio.sleep(3)


    async def _receive_loop(self, ws):
        """Receive messages in a loop and handle them."""
        while not self.stop_event.is_set():
            try:
                #raw_msg = await asyncio.wait_for(ws.recv(), timeout=4.0)
                raw_msg = await ws.recv()
                self._log_message_received(raw_msg)
                #pprint(f"[{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nRECEIVED: {raw_msg}")
                self._handle_message(raw_msg)
            except asyncio.TimeoutError: 
                # Periodic check if we should stop
                continue
            except websockets.ConnectionClosed:
                print("WebSocket connection closed.")
                ws = None
                self._uninitialize_current_state()
                self.state_change_callback({"isWsConnected": False})
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    def _handle_message(self, raw_msg: str):
        """Parse and act on the incoming messages."""
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            print(f"Received non-JSON message: {raw_msg}")
            return

        # Handle known responses
        if "requestId" in data and "response" in data:
            # This is a pairing or action response
            print(f"Received response for requestId={data['requestId']}: {data['response']}")
            if data["response"] == "Pairing response resulted in no action":
                print("Pairing seems to have failed or was not needed.")
            elif data["response"] == "Success":
                print("Action success!")
            return

        # Handle token refresh
        if "tokenRefresh" in data:
            new_token = data["tokenRefresh"]
            print(f"Received tokenRefresh: {new_token}")
            self.token = new_token
            self._save_token(new_token)
            return

        # Handle meetingUpdate
        if "meetingUpdate" in data:
            meeting_update = data["meetingUpdate"]
            self._process_meeting_update(meeting_update)

    def _process_meeting_update(self, meeting_update: dict):
        meeting_state = meeting_update.get("meetingState", {})
        inMeeting = meeting_state.get("isInMeeting", False)
        if not inMeeting:
            meeting_state["isMuted"] = True

    # Handle first time cases where the current state is None
        changed_states_dict = {}

        for key, value in meeting_state.items():
            if key in self.current_state:
                if value != self.current_state[key]:
                    changed_states_dict[key] = value
                    self.current_state[key] = value

        if changed_states_dict:
            print(f"State changed: {changed_states_dict}")
            if self.state_change_callback:
                self.state_change_callback(changed_states_dict)


    async def _close_ws(self):
        """Attempt to close the WebSocket if needed."""
        # This will terminate the loop in _receive_loop by raising ConnectionClosed
        pass

    def _send_message(self, message: dict):
        """Enqueue a message to be sent on the WebSocket connection."""
        # Because websockets is async, we must schedule this in the event loop
        if hasattr(self, "loop") and self.loop.is_running():
            self._log_message_send(message)
            #pprint(f"[{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nSENT: {message}")
            asyncio.run_coroutine_threadsafe(self._async_send(message), self.loop)
        else:
            print("WebSocket not connected or loop not running, cannot send message.")

    async def _async_send(self, message: dict):
        """Send the message over the WebSocket in the async loop."""
        if  self.current_state["isWsConnected"] == False:
            print("WebSocket not connected, cannot send message.")
            return 
        await self.ws.send(json.dumps(message))


# --------------------------------------------------------
#                  CALLBACK EXAMPLES
# --------------------------------------------------------
def on_state_change_callback(state: dict):
    print(f"State changed: {state}")

def main():
    # Instantiate the client with optional callbacks
    client = TeamsMeetingClient(
        state_change_callback=on_state_change_callback
    )

    print("Welcome to the TeamsMeetingClient CLI!")
    print("Type 'help' for a list of commands.")
    while True:
        cmd = input("> ").strip().split()
        if not cmd:
            continue  # Empty input

        # Break the loop on "quit"/"exit"
        if cmd[0].lower() in ["quit", "exit", "q"]:
            break
        
        elif cmd[0].lower() == "help":
            print("""
Available commands:
  start               - Start the WebSocket client (connect)
  stop                - Stop the WebSocket client (disconnect)
  pair                - Send a pairing request
  command <action> <parameters> - Send a custom command   
  reaction <type>     - Send a reaction (e.g., "reaction like")
  toggle-video        - Toggle video on/off
  camera <on/off>     - Turn camera on/off
  toggle-mute         - Toggle mute on/off
  microphone <on/off> - Turn microphone on/off
  toggle-hand         - Raise/lower hand
  toggle-background   - Toggle background blur
  leave-call          - Leave the current call
  help                - Show this help message
  quit or exit        - Quit the program
""")

        elif cmd[0].lower() == "start":
            client.start()

        elif cmd[0].lower() == "stop":
            client.stop()

        elif cmd[0].lower() == "pair":
            client.send_pairing_request()

        elif cmd[0].lower() == "reaction":
            if len(cmd) < 2:
                print("[ERROR] Usage: reaction <type>")
            else:
                reaction_type = cmd[1]
                client.send_reaction(reaction_type)
        elif cmd[0].lower() == "command":
            if len(cmd) < 2:
                print("[ERROR] Usage: command <action> <parameters>")
            else:
                action = cmd[1]
                parameters = {}
                if len(cmd) > 2:
                    # Parse additional parameters as key-value pairs
                    for param in cmd[2:]:
                        key, value = param.split("=")
                        parameters[key] = value
                client.send_custom_command(action, parameters)

        elif cmd[0].lower() == "toggle-video":
            client.toggle_video()

        elif cmd[0].lower() == "toggle-mute":
            client.toggle_mute()

        elif cmd[0].lower() == "camera":
            client.set_camera(True if cmd[1] == "on" else False)

        elif cmd[0].lower() == "microphone":
            client.set_microphone(True if cmd[1] == "on" else False)

        elif cmd[0].lower() == "toggle-hand":
            client.toggle_hand()

        elif cmd[0].lower() == "toggle-background":
            client.toggle_background_blur()

        elif cmd[0].lower() == "leave-call":
            client.leave_call()

        else:
            print(f"[ERROR] Unknown command '{cmd[0]}'. Type 'help' for usage.")

    # When loop ends, stop the client and exit
    client.stop()
    print("Exiting. Goodbye!")

if __name__ == "__main__":
    main()