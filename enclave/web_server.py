"""
Modern Web GUI Server for Enclave.
Provides WhatsApp-like interface with real-time messaging, file sharing, and peer management.
"""

import os
import json
import time
import base64
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import getpass

from . import keystore, network, message as msg_module, crypto

# Flask app setup
app = Flask(__name__,
            template_folder='../web/templates',
            static_folder='../web/static')
app.config['SECRET_KEY'] = os.urandom(24)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
chat_server = None
private_key = None
public_key = None
my_fingerprint = None
peers = {}  # {fingerprint: {'host': str, 'port': int, 'name': str, 'online': bool}}
message_history = {}  # {fingerprint: [{msg}, {msg}, ...]}
MESSAGES_FILE = Path("keys/messages.json")


def load_message_history():
    """Load message history from disk."""
    global message_history
    if MESSAGES_FILE.exists():
        try:
            with open(MESSAGES_FILE, 'r') as f:
                message_history = json.load(f)
        except:
            message_history = {}
    else:
        message_history = {}


def save_message_history():
    """Save message history to disk."""
    try:
        MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(message_history, f, indent=2)
    except Exception as e:
        print(f"Failed to save message history: {e}")


def add_to_history(peer_fingerprint, message_text, sent=False, timestamp=None):
    """Add message to history."""
    if peer_fingerprint not in message_history:
        message_history[peer_fingerprint] = []

    msg_entry = {
        'text': message_text,
        'sent': sent,
        'timestamp': timestamp or time.time(),
        'time_str': datetime.fromtimestamp(timestamp or time.time()).strftime('%I:%M %p')
    }

    message_history[peer_fingerprint].append(msg_entry)

    # Keep last 1000 messages per peer
    if len(message_history[peer_fingerprint]) > 1000:
        message_history[peer_fingerprint] = message_history[peer_fingerprint][-1000:]

    save_message_history()


def message_received_callback(sender_fingerprint, plaintext, timestamp):
    """Callback when message is received from network layer."""
    # Add to history
    add_to_history(sender_fingerprint, plaintext, sent=False, timestamp=timestamp)

    # Emit to web clients via WebSocket
    socketio.emit('new_message', {
        'from': sender_fingerprint,
        'text': plaintext,
        'timestamp': timestamp,
        'time_str': datetime.fromtimestamp(timestamp).strftime('%I:%M %p')
    })

    print(f"[WebGUI] Message from {sender_fingerprint[:12]}: {plaintext}")


def load_peers_from_disk():
    """Load peer information from disk."""
    global peers
    peers_dir = Path("keys/peers")

    if not peers_dir.exists():
        return

    for address_file in peers_dir.glob("*.address"):
        fingerprint = address_file.stem
        address = address_file.read_text().strip()

        if ':' in address:
            host, port_str = address.rsplit(':', 1)
            try:
                port = int(port_str)
                peers[fingerprint] = {
                    'host': host,
                    'port': port,
                    'name': fingerprint[:12],
                    'online': False,
                    'last_seen': None
                }
            except ValueError:
                continue


# Flask routes
@app.route('/')
def index():
    """Serve main chat interface."""
    return render_template('index.html')


@app.route('/api/me')
def get_my_info():
    """Get current user information."""
    return jsonify({
        'fingerprint': my_fingerprint,
        'short_fingerprint': my_fingerprint[:12] if my_fingerprint else None,
        'peers_count': len(peers)
    })


@app.route('/api/peers')
def get_peers():
    """Get list of all peers."""
    peer_list = []
    for fp, info in peers.items():
        peer_list.append({
            'fingerprint': fp,
            'short_fingerprint': fp[:12],
            'name': info.get('name', fp[:12]),
            'host': info['host'],
            'port': info['port'],
            'online': info.get('online', False),
            'unread': 0  # TODO: implement unread count
        })

    return jsonify({'peers': peer_list})


@app.route('/api/peers/<fingerprint>/messages')
def get_messages(fingerprint):
    """Get message history with a specific peer."""
    messages = message_history.get(fingerprint, [])
    return jsonify({'messages': messages})


@app.route('/api/peers/<fingerprint>/send', methods=['POST'])
def send_message(fingerprint):
    """Send message to a peer."""
    data = request.json
    message_text = data.get('message', '')

    if not message_text:
        return jsonify({'error': 'Message is empty'}), 400

    if fingerprint not in peers:
        return jsonify({'error': 'Peer not found'}), 404

    peer_info = peers[fingerprint]

    # Send in background thread
    def send_thread():
        try:
            network.send_message(
                peer_info['host'],
                peer_info['port'],
                fingerprint,
                message_text,
                private_key,
                my_fingerprint
            )

            # Add to history
            add_to_history(fingerprint, message_text, sent=True)

            # Notify web clients
            socketio.emit('message_sent', {
                'to': fingerprint,
                'text': message_text,
                'timestamp': time.time()
            })

        except Exception as e:
            socketio.emit('message_error', {
                'to': fingerprint,
                'error': str(e)
            })

    thread = threading.Thread(target=send_thread, daemon=True)
    thread.start()

    return jsonify({'success': True})


@app.route('/api/peers/add', methods=['POST'])
def add_peer():
    """Add new peer."""
    data = request.json
    peer_name = data.get('name', '')
    peer_host = data.get('host', '')
    peer_port = data.get('port', '')
    public_key_data = data.get('public_key', '')

    if not all([peer_host, peer_port, public_key_data]):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        # Save public key to temp file
        temp_key_file = Path(f"keys/temp_peer_key_{int(time.time())}.pem")
        temp_key_file.write_text(public_key_data)

        # Add peer key
        fingerprint = keystore.add_peer_key(str(temp_key_file))

        # Save address
        address = f"{peer_host}:{peer_port}"
        address_file = Path(f"keys/peers/{fingerprint}.address")
        address_file.write_text(address)

        # Add to peers dict
        peers[fingerprint] = {
            'host': peer_host,
            'port': int(peer_port),
            'name': peer_name or fingerprint[:12],
            'online': False
        }

        # Clean up temp file
        temp_key_file.unlink()

        # Reload key into cache
        keystore.load_peer_key(fingerprint)

        return jsonify({
            'success': True,
            'fingerprint': fingerprint,
            'short_fingerprint': fingerprint[:12]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/broadcast', methods=['POST'])
def broadcast_message():
    """Broadcast message to all peers."""
    data = request.json
    message_text = data.get('message', '')

    if not message_text:
        return jsonify({'error': 'Message is empty'}), 400

    if not peers:
        return jsonify({'error': 'No peers available'}), 400

    # Send in background
    def broadcast_thread():
        recipients = [(info['host'], info['port'], fp)
                     for fp, info in peers.items()]

        results, errors = network.send_batch_messages(
            recipients,
            message_text,
            private_key,
            my_fingerprint
        )

        # Add to history for each peer
        for fp in peers.keys():
            add_to_history(fp, message_text, sent=True)

        # Notify clients
        socketio.emit('broadcast_complete', {
            'success_count': sum(1 for v in results.values() if v),
            'total': len(results)
        })

    thread = threading.Thread(target=broadcast_thread, daemon=True)
    thread.start()

    return jsonify({'success': True})


@app.route('/api/export/public-key')
def export_public_key():
    """Export user's public key for sharing."""
    try:
        public_key_path = Path("keys/my_public_key.pem")
        if not public_key_path.exists():
            return jsonify({'error': 'Public key not found'}), 404

        public_key_data = public_key_path.read_text()

        return jsonify({
            'public_key': public_key_data,
            'fingerprint': my_fingerprint
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"[WebGUI] Client connected: {request.sid}")
    emit('connected', {'fingerprint': my_fingerprint})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"[WebGUI] Client disconnected: {request.sid}")


@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator."""
    emit('peer_typing', data, broadcast=True, include_self=False)


def start_web_server(host='0.0.0.0', port=5000, password=None):
    """
    Start the web GUI server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port for web interface (default: 5000)
        password: Password to unlock keys (if None, will prompt)
    """
    global chat_server, private_key, public_key, my_fingerprint

    # Load user keys
    if password is None:
        password = getpass.getpass("Enter password to unlock private key: ")

    try:
        private_key, public_key, my_fingerprint = keystore.load_my_keys(password)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"\n{'='*60}")
    print(f"Enclave Web GUI Starting...")
    print(f"Your fingerprint: {my_fingerprint}")
    print(f"{'='*60}\n")

    # Load message history
    load_message_history()

    # Preload peer keys
    print("Loading peer keys...")
    keystore.preload_all_peer_keys()

    # Load peers
    load_peers_from_disk()
    print(f"Loaded {len(peers)} peer(s)")

    # Start P2P chat server
    chat_port = 8000  # Default P2P port
    chat_server = network.ChatServer(
        host='0.0.0.0',
        port=chat_port,
        private_key=private_key,
        public_key=public_key,
        fingerprint=my_fingerprint,
        message_callback=message_received_callback,
        max_workers=20
    )

    chat_server.start()

    # Start Flask web server
    print(f"\n{'='*60}")
    print(f"🌐 Web GUI available at: http://localhost:{port}")
    print(f"📡 P2P Server listening on port: {chat_port}")
    print(f"{'='*60}\n")

    try:
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        chat_server.stop()


if __name__ == '__main__':
    start_web_server()
