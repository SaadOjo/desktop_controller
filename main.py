from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'

# Initialize SocketIO
socketio = SocketIO(app)

# State storage
state = {
    "buttons": {"mic": False, "cam": False},  # Buttons with their states
    "sliders": {"vol": 50, "bright": 50}     # Sliders with initial values
}

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


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('button-toggle')
def handle_button_toggle(data):
    print(f"Button toggled: {data}")
    button_id = data.get("id")

    if button_id in state["buttons"]:
        # Toggle the button state on the server
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
