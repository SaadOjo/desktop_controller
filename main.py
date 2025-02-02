#import eventlet
#eventlet.monkey_patch()  # Must be called before other imports that you want to be patched

from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from teams_meeting_client import TeamsMeetingClient
import time
import threading
import queue
# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'

# Initialize SocketIO
socketio = SocketIO(app, async_mode="threading")
#socketio = SocketIO(app)
print("Async mode is:", socketio.async_mode)

message_queue = queue.Queue()

connected_clients = set()

def message_queue_handler():
    while True:
        if len(connected_clients) == 0:
            print("No clients connected, waiting...")
            time.sleep(1)
            continue
        message = message_queue.get()
        print(f"Message in queue: {message}")
        socketio.emit(message["event"], message["data"], namespace='/')


def queue_emit(event_name, data):
    #place message in queue
    message_queue.put({"event": event_name, "data": data})


def on_state_change_callback(state_changes_dict):
    for key,value in state_changes_dict.items():
        match key:
            case "isWsConnected":
                queue_emit("set-led-state", {"id": "connected", "state": value})
            case "isInMeeting":
                queue_emit("set-led-state", {"id": "meeting", "state": value})
            case "isVideoOn":
                queue_emit("set-button-state", {"id": "cam", "state": value})
            case "isMuted":
                queue_emit("set-button-state", {"id": "mic", "state": not value})

# State storage
state = {
    "sliders": {"vol": 50, "bright": 50},     # Sliders with initial values
}


myClient = TeamsMeetingClient(state_change_callback=on_state_change_callback)
myClient.start()

#start the message queue handler in a background thread
message_queue_thread = threading.Thread(target=message_queue_handler, daemon=True) 
message_queue_thread.start()

#need to figure out how to properly manage the lifecycle of the thread

# HTTP route to render the web page
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('onConnect: Client connected')
    connected_clients.add(request.sid)
    teams_client_state = myClient.get_full_state()
    on_state_change_callback(teams_client_state)

    for slider_id, slider_value in state["sliders"].items():
        queue_emit("set-slider-value", {"id": slider_id, "value": slider_value})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    connected_clients.remove(request.sid)


@socketio.on('button-toggle')
def handle_button_toggle(data):
    print(f"Button toggled: {data}")
    button_id = data.get("id")

    match button_id:
        case "mic":
            myClient.toggle_mute()
        case "cam":
            myClient.toggle_video()

@socketio.on('slider-change')
def handle_slider_change(data):
    print(f"Slider changed: {data}")
    slider_id = data.get("id")
    slider_value = data.get("value")

    if slider_id in state["sliders"]:
        # Update the slider value on the server
        state["sliders"][slider_id] = slider_value
        # Broadcast the updated slider value to all clients
        queue_emit("set-slider-value", {"id": slider_id, "value": slider_value})



# Run the Flask app with WebSocket support
if __name__ == '__main__':
    print("\n\n\n\n\n\n Starting Flask app....")
    socketio.run(app, host='0.0.0.0', port=80, debug=True)

