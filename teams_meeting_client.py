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
        device: str = "Desktop Controller",
        app: str = "Desktop Controller App",
        app_version: str = "1.0.00",
        meeting_started_callback: Optional[Callable[[], None]] = None,
        meeting_ended_callback: Optional[Callable[[], None]] = None,
        on_connect_callback: Optional[Callable[[], None]] = None,
        on_disconnect_callback: Optional[Callable[[], None]] = None
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
        self.meeting_started_callback = meeting_started_callback
        self.meeting_ended_callback = meeting_ended_callback
        self.on_connect_callback = on_connect_callback
        self.on_disconnect_callback = on_disconnect_callback

        # Load token from file if available, else use default
        self.token = self._load_token()

        # Track the current "canPair" state (assuming True=not in meeting, False=in meeting)
        self.can_pair = None  # By default, assume not in a meeting
        
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

    def toggle_mute(self):
        action_data = {
            "action": "toggle-mute",
            "parameters": {},
            "requestId": self._get_request_id()
        }
        self._send_message(action_data)

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

    def _get_current_time_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    def _log_message_send(self, message):
        pprint(f"\n[bold red][{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nSENT: {message} [/bold red]")

    def _log_message_received(self, message):
        pprint(f"\n[bold green][{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nRECEIVED: {json.loads(message)} [/bold green]")
    def _get_request_id(self) -> int:
        current_id = self.request_id_counter
        self.request_id_counter += 1
        return current_id

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
        """Establish WebSocket connection and handle incoming messages."""
        try:
            async with websockets.connect(self.ws_url) as ws:
                print(f"Connected to {self.ws_url}")
                if self.on_connect_callback:
                    self.on_connect_callback()
                # Listen for messages until stop_event is set
                await self._receive_loop(ws)
        except Exception as e:
            print(f"WebSocket connection failed: {e}")

    async def _receive_loop(self, ws):
        """Receive messages in a loop and handle them."""
        while not self.stop_event.is_set():
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                self._log_message_received(raw_msg)
                #pprint(f"[{self._get_current_time_str()}] THREAD: {threading.current_thread().name}. \nRECEIVED: {raw_msg}")
                self._handle_message(raw_msg)
            except asyncio.TimeoutError: 
                # Periodic check if we should stop
                continue
            except websockets.ConnectionClosed:
                print("WebSocket connection closed.")
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
        """Look at 'canPair' to determine if in a meeting or not."""
        meeting_permissions = meeting_update.get("meetingPermissions", {})
        can_pair_now = meeting_permissions.get("canPair", True)

        # If canPair changes from True -> False, meeting started
        # If canPair changes from False -> True, meeting ended

        if self.can_pair is None:
            # First update, set the initial state
            self.can_pair = can_pair_now

            if not can_pair_now:
                # Meeting started
                if self.meeting_ended_callback:
                    self.meeting_ended_callback()
            else:
                # Meeting ended
                if self.meeting_started_callback:
                    self.meeting_started_callback()
            return

        if can_pair_now != self.can_pair:
            self.can_pair = can_pair_now
            if not can_pair_now:
                # Meeting started
                if self.meeting_ended_callback:
                    self.meeting_ended_callback()
            else:
                # Meeting ended
                if self.meeting_started_callback:
                    self.meeting_started_callback()

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
        try:
            async with websockets.connect(self.ws_url) as ws:
                # This approach opens a new connection for each send,
                # which might not be ideal depending on your setup.
                # Typically, you’d keep a persistent connection.
                # For demonstration, we open a new connection each time.
                await ws.send(json.dumps(message))
        except Exception as e:
            print(f"Failed to send message: {e}")


# --------------------------------------------------------
#                  CALLBACK EXAMPLES
# --------------------------------------------------------
def on_meeting_start():
    print("[CALLBACK] Meeting started!")

def on_meeting_end():
    print("[CALLBACK] Meeting ended!")

def main():
    # Instantiate the client with optional callbacks
    client = TeamsMeetingClient(
        meeting_started_callback=on_meeting_start,
        meeting_ended_callback=on_meeting_end
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
  reaction <type>     - Send a reaction (e.g., "reaction like")
  toggle-video        - Toggle video on/off
  toggle-mute         - Toggle mute on/off
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

        elif cmd[0].lower() == "reaction":
            if len(cmd) < 2:
                print("[ERROR] Usage: reaction <type>")
            else:
                reaction_type = cmd[1]
                client.send_reaction(reaction_type)

        elif cmd[0].lower() == "toggle-video":
            client.toggle_video()

        elif cmd[0].lower() == "toggle-mute":
            client.toggle_mute()

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