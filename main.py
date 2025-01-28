from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit
from teams_meeting_client import TeamsMeetingClient

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'

# Initialize SocketIO
socketio = SocketIO(app)

def on_meeting_start():
    print("XXXXX: Meeting started")
    #state["leds"]["meeting"] = True
    socketio.emit("set-led-state", {"id": "meeting", "state": True})

def on_meeting_end():
    print("XXXXX: Meeting ended")
    #state["leds"]["meeting"] = False
    socketio.emit("set-led-state", {"id": "meeting", "state": False})   
    
def on_client_connect():
    print("Client connected")
    state["leds"]["connected"] = True
    socketio.emit("set-led-state", {"id": "connected", "state": True})

myClient = TeamsMeetingClient(meeting_started_callback=on_meeting_start, meeting_ended_callback=on_meeting_end, on_connect_callback=on_client_connect)
myClient.start()

# State storage
state = {
    "buttons": {"mic": False, "cam": False},  # Buttons with their states
    "sliders": {"vol": 50, "bright": 50},     # Sliders with initial values
    "leds": {"meeting": False, "connected": False}  # LEDs with their states
}

@app.teardown_appcontext
def cleanup(exception=None):
    print("Cleaning up resources...")
    myClient.stop()
    # Add cleanup code here, such as closing database connections
    # or releasing any global resources.

# HTTP route to render the web page
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send the initial state to the connected client
    for button_id, state_value in state["buttons"].items():
        socketio.emit("set-button-state", {"id": button_id, "state": state_value})
    for slider_id, slider_value in state["sliders"].items():
        socketio.emit("set-slider-value", {"id": slider_id, "value": slider_value})
    #for led_id, led_state in state["leds"].items():
    #    socketio.emit("set-led-state", {"id": led_id, "state": led_state})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('button-toggle')
def handle_button_toggle(data):
    print(f"Button toggled: {data}")
    button_id = data.get("id")

    if button_id in state["buttons"]:
        # Toggle the button state on the server
        match button_id:
            case "mic":
                myClient.toggle_mic()
            case "cam":
                myClient.toggle_cam()

        state["buttons"][button_id] = not state["buttons"][button_id]
        # Broadcast the updated state to all clients
        socketio.emit("set-button-state", {"id": button_id, "state": state["buttons"][button_id]})

@socketio.on('slider-change')
def handle_slider_change(data):
    print(f"Slider changed: {data}")
    slider_id = data.get("id")
    slider_value = data.get("value")

    if slider_id in state["sliders"]:
        # Update the slider value on the server
        state["sliders"][slider_id] = slider_value
        # Broadcast the updated slider value to all clients
        socketio.emit("set-slider-value", {"id": slider_id, "value": slider_value})





# Run the Flask app with WebSocket support
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=True)
