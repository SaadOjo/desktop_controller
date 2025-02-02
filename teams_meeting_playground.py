import asyncio
import threading
import time
import logging
import json
import websockets
from typing import Optional, Callable, Dict

logging.basicConfig(level=logging.INFO)

class WebSocketManager:
    def __init__(
        self,
        reconnect_interval: float = 30.0,
        on_ws_connected: Optional[Callable[[], None]] = None,
        on_ws_disconnected: Optional[Callable[[], None]] = None,
        on_meeting_started: Optional[Callable[[], None]] = None,
        on_meeting_ended: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[Dict], None]] = None
    ):
        """
        :param reconnect_interval: How often (in seconds) to attempt reconnects.
        :param on_ws_connected: Callback when WebSocket connection is established.
        :param on_ws_disconnected: Callback when WebSocket is closed or fails.
        :param on_meeting_started: Callback when a meeting starts.
        :param on_meeting_ended: Callback when a meeting ends.
        :param on_state_change: Callback for any change in the meeting state (receives dict).
        """
        self._ws_uri = None
        self._loop = None
        self._ws = None
        self._stop_event = threading.Event()
        self._thread = None

        # Connection status flags
        self._is_connecting = False
        self._is_connected = False

        # Callbacks
        self.on_ws_connected = on_ws_connected
        self.on_ws_disconnected = on_ws_disconnected
        self.on_meeting_started = on_meeting_started
        self.on_meeting_ended = on_meeting_ended
        self.on_state_change = on_state_change

        # Reconnect settings
        self._reconnect_interval = reconnect_interval

        # Basic meeting state
        self._meeting_state = {
            "isInMeeting": False,
            "isMuted": False,
            "isCameraOn": False,
            "isHandRaised": False,
            "isRecordingOn": False,
            "isBackgroundBlurred": False,
            "isSharing": False,
        }

    def start(self, ws_uri: str):
        """
        Start the background thread and connect to the WebSocket.
        :param ws_uri: WebSocket URI (e.g. "ws://localhost:8124")
        """
        if self._thread and self._thread.is_alive():
            logging.warning("WebSocketManager is already running.")
            return

        self._ws_uri = ws_uri
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """
        Signal the background thread to stop and close the WebSocket gracefully.
        """
        logging.info("Stopping WebSocketManager...")
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close_ws(), self._loop)

        if self._thread:
            self._thread.join()
        logging.info("WebSocketManager stopped.")

    def send_message(self, message: dict):
        """
        Enqueue a dictionary message to be sent over the WebSocket.
        """
        if not self._loop or not self._ws or not self._is_connected:
            logging.warning("WebSocket not connected; cannot send message.")
            return

        # Schedule sending in the event loop
        asyncio.run_coroutine_threadsafe(self._async_send(message), self._loop)

    # -------------------------------------------------------------------------
    # Internal methods
    # -------------------------------------------------------------------------

    def _run_loop(self):
        """
        Main entry point for the background thread:
          1. Create an event loop
          2. Run _main_task() until stopped
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._main_task())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"WebSocketManager loop error: {e}")
        finally:
            self._loop.run_until_complete(self._cleanup())
            self._loop.close()

    async def _main_task(self):
        """
        High-level task that:
          - Tries to connect
          - Listens for messages
          - Reconnects if necessary
        """
        while not self._stop_event.is_set():
            try:
                await self._connect()
                await self._receive_loop()
            except Exception as ex:
                logging.warning(f"WebSocket error: {ex}")
            finally:
                await self._disconnect_callback()
            
            # Wait before attempting reconnect
            logging.info(f"Reconnecting in {self._reconnect_interval} seconds...")
            await asyncio.sleep(self._reconnect_interval)

    async def _connect(self):
        """
        Attempt to connect to the WebSocket.
        """
        if self._is_connecting or self._is_connected:
            return

        logging.info(f"Connecting to {self._ws_uri}...")
        self._is_connecting = True
        try:
            self._ws = await websockets.connect(self._ws_uri)
            self._is_connected = True
            self._is_connecting = False

            # Fire connected callback
            if self.on_ws_connected:
                self.on_ws_connected()

            logging.info("WebSocket connected.")
        except Exception as e:
            self._is_connecting = False
            self._is_connected = False
            logging.error(f"Failed to connect: {e}")
            # We'll retry in the main loop
            raise

    async def _receive_loop(self):
        """
        Continuously receive messages from the server until disconnected or error.
        """
        while self._ws and not self._stop_event.is_set():
            try:
                msg = await self._ws.recv()
                if msg is None:
                    # Connection might have closed
                    logging.warning("WebSocket received None, closing...")
                    break

                await self._handle_message(msg)
            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                logging.warning("WebSocket connection closed.")
                break
            except Exception as e:
                logging.error(f"Error in receive loop: {e}")
                break

    async def _close_ws(self):
        """
        Close the WebSocket gracefully if open.
        """
        if self._ws and not self._ws.closed:
            logging.info("Closing WebSocket connection...")
            await self._ws.close()
        self._ws = None
        self._is_connected = False

    async def _cleanup(self):
        """
        Called on final shutdown of the event loop.
        """
        logging.info("Cleaning up WebSocketManager...")
        await self._close_ws()

    async def _disconnect_callback(self):
        """
        Cleanup state and invoke disconnection callback if needed.
        """
        if self._is_connected:
            logging.info("WebSocket disconnected.")
        self._is_connected = False

        if self.on_ws_disconnected:
            self.on_ws_disconnected()

    async def _async_send(self, message: dict):
        """
        Send a JSON-encoded message over the WebSocket (async).
        """
        if not self._ws:
            logging.warning("No WebSocket to send on.")
            return

        try:
            payload = json.dumps(message)
            await self._ws.send(payload)
            logging.debug(f"Sent message: {payload}")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

    async def _handle_message(self, raw_msg: str):
        """
        Parse the incoming message, handle meeting updates, or any custom logic.
        """
        logging.info(f"Received message: {raw_msg}")
        try:
            data = json.loads(raw_msg)
        except json.JSONDecodeError:
            logging.warning(f"Non-JSON message received: {raw_msg}")
            return

        # Example: Check if there's a "meetingUpdate"
        if "meetingPermissions" in data or "meetingState" in data:
            # This is just an example of how to interpret the message
            # based on your original code references:
            await self._process_meeting_update(data)

    async def _process_meeting_update(self, data: dict):
        """
        Update local meeting state and call relevant callbacks.
        """
        meeting_state = data.get("meetingState", {})
        # For example, check 'isInMeeting'
        is_in_meeting = meeting_state.get("isInMeeting", False)

        # Check if state changed from not in meeting -> in meeting
        if is_in_meeting and not self._meeting_state["isInMeeting"]:
            # Meeting started
            if self.on_meeting_started:
                self.on_meeting_started()

        # Check if state changed from in meeting -> not in meeting
        if not is_in_meeting and self._meeting_state["isInMeeting"]:
            # Meeting ended
            if self.on_meeting_ended:
                self.on_meeting_ended()

        # Update local meeting state
        for key in self._meeting_state.keys():
            if key in meeting_state:
                self._meeting_state[key] = meeting_state[key]

        # Fire "on_state_change" callback with the new state
        if self.on_state_change:
            self.on_state_change(self._meeting_state)

    # -------------------------------------------------------------------------
    # Public utility methods (matching C# style for demonstration)
    # -------------------------------------------------------------------------

    async def send_reaction_to_teams(self, reaction_type: str):
        """
        Send a reaction command (like 'like', 'applause', etc.)
        """
        action_data = {
            "action": "send-reaction",
            "parameters": {"type": reaction_type},
            "requestId": 123  # or any unique ID
        }
        self.send_message(action_data)

    async def disconnect(self):
        """
        Public method to initiate a manual disconnect.
        """
        if self._loop and self._loop.is_running():
            await asyncio.run_coroutine_threadsafe(self._close_ws(), self._loop)

###################################################
# Actual "TeamsMeetingClient" that we can CLI around
###################################################
class TeamsMeetingClient:
    def __init__(
        self,
        ws_url: str = "ws://localhost:8124",
        meeting_started_callback: Optional[Callable[[], None]] = None,
        meeting_ended_callback: Optional[Callable[[], None]] = None,
        ws_connected_callback: Optional[Callable[[], None]] = None,
        ws_disconnected_callback: Optional[Callable[[], None]] = None
    ):
        """
        Simple wrapper around WebSocketManager with the desired callbacks.
        """
        # Replace "MockWebSocketManager" with your real "WebSocketManager" class.
        self.ws_manager = WebSocketManager(
            on_ws_connected=ws_connected_callback,
            on_ws_disconnected=ws_disconnected_callback,
            on_meeting_started=meeting_started_callback,
            on_meeting_ended=meeting_ended_callback
        )
        self.ws_url = ws_url

    def start(self):
        """Connect to the WebSocket server."""
        self.ws_manager.start(self.ws_url)

    def stop(self):
        """Disconnect from the WebSocket server."""
        self.ws_manager.stop()

    def send_reaction(self, reaction_type: str):
        """Send a reaction (like 'like', 'applause', etc.)."""
        self.ws_manager.send_reaction_to_teams(reaction_type)

    def toggle_video(self):
        self.ws_manager.toggle_video()

    def toggle_mute(self):
        self.ws_manager.toggle_mute()

    def toggle_hand(self):
        self.ws_manager.toggle_hand()

    def toggle_background_blur(self):
        self.ws_manager.toggle_background_blur()

    def leave_call(self):
        self.ws_manager.leave_call()


###################################################
# CALLBACK EXAMPLES
###################################################
def on_meeting_start():
    print("[CALLBACK] Meeting started!")

def on_meeting_end():
    print("[CALLBACK] Meeting ended!")

def on_ws_connected():
    print("[CALLBACK] WebSocket connected!")

def on_ws_disconnected():
    print("[CALLBACK] WebSocket disconnected!")


###################################################
# CLI MAIN FUNCTION
###################################################
def main():
    # Instantiate the client with optional callbacks
    client = TeamsMeetingClient(
        ws_url="ws://localhost:8124",  # Modify if needed
        meeting_started_callback=on_meeting_start,
        meeting_ended_callback=on_meeting_end,
        ws_connected_callback=on_ws_connected,
        ws_disconnected_callback=on_ws_disconnected
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
