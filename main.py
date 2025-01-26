from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'

# Initialize SocketIO
socketio = SocketIO(app)

# HTTP route to render the web page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dummy')
def dummy():
    return render_template('dummy.html')

# WebSocket event for receiving and sending messages
@socketio.on('message')
def handle_message(message):
    print(f"Received message: {message}")
    send(f"Server says: {message}", broadcast=True)

# WebSocket custom event
@socketio.on('custom_event')
def handle_custom_event(data):
    print(f"Received custom event data: {data}")
    emit('response', {'msg': f"Server received: {data['msg']}"}, broadcast=True)

# Run the Flask app with WebSocket support
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=True)
