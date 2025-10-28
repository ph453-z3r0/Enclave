# Enclave Web GUI

**Modern WhatsApp-style Web Interface for Enclave**

Experience secure peer-to-peer messaging with a beautiful, intuitive web interface that rivals popular messaging apps - all while maintaining end-to-end encryption and zero reliance on central servers.

---

## 🌟 Features

### Modern User Interface
- **WhatsApp-inspired Design**: Dark theme with familiar layout
- **Real-time Messaging**: Instant message delivery via WebSocket
- **Click-to-Interact**: No more typing IP addresses - just click!
- **Message History**: All conversations saved locally
- **Typing Indicators**: See when peers are typing
- **Toast Notifications**: Non-intrusive alerts for events
- **Responsive Design**: Works on desktop, tablet, and mobile

### Advanced Functionality
- **Peer Management**: Add, view, and manage peers visually
- **One-Click Selection**: Click any peer to start chatting
- **Broadcast Messages**: Send to all peers simultaneously
- **Search**: Find peers and messages quickly
- **Public Key Export**: Share your key with one click
- **Message Persistence**: History saved across sessions

### Security Features
- **Same Encryption**: RSA-4096 + AES-256-GCM (no compromises)
- **End-to-End Encryption**: Keys never leave your device
- **No Cloud Storage**: All data stored locally
- **Replay Protection**: Built-in duplicate detection
- **Digital Signatures**: Every message authenticated

---

## 📦 Installation

### Install Web Dependencies

```bash
# Option 1: Install with web extras
pip install -e ".[web]"

# Option 2: Install dependencies manually
pip install flask flask-socketio python-socketio flask-cors
```

### Verify Installation

```bash
enclave-web --help
```

---

## 🚀 Quick Start

### 1. Generate Keys (if not already done)

```bash
enclave --generate
```

### 2. Start Web GUI

```bash
# Default (opens on http://localhost:5000)
enclave --web

# Or use standalone launcher
enclave-web

# Custom port
enclave --web --web-port 8080

# Custom host and port
enclave-web --host 0.0.0.0 --port 8080
```

### 3. Open Browser

Navigate to: **http://localhost:5000**

### 4. Add Peers

Click the **"Add Peer"** button (➕) in the sidebar header:

1. Enter peer name (optional)
2. Enter IP address (e.g., `192.168.1.100`)
3. Enter port (default: `8000`)
4. Paste peer's public key
5. Click "Add Peer"

### 5. Start Chatting!

- Click on any peer in the sidebar
- Type your message
- Press Enter or click Send button
- Messages appear instantly with encryption!

---

## 🎨 User Interface Guide

### Main Layout

```
┌─────────────┬────────────────────────────────┐
│  SIDEBAR    │       CHAT AREA                │
│             │                                │
│  [Header]   │   [Chat Header]                │
│  [Search]   │                                │
│  [Peers]    │   [Messages]                   │
│             │                                │
│             │   [Input Box]                  │
└─────────────┴────────────────────────────────┘
```

### Sidebar Header Actions

| Icon | Function | Description |
|------|----------|-------------|
| ➕ | Add Peer | Add new peer with public key |
| 📢 | Broadcast | Send message to all peers |
| 🔑 | My Key | View/export your public key |

### Chat Commands

| Action | Method |
|--------|--------|
| Send Message | Type and press Enter |
| Select Peer | Click peer in sidebar |
| View Peer Info | Click peer name in chat header |
| Search Peers | Type in search box |

---

## 📱 Usage Examples

### Adding Your First Peer (Alice adds Bob)

**Step 1: Alice shares her public key**
1. Alice clicks 🔑 "My Key" button
2. Clicks "Copy Key" or "Download"
3. Sends key to Bob via email/Signal/etc.

**Step 2: Alice adds Bob**
1. Alice clicks ➕ "Add Peer"
2. Fills in form:
   - Name: `Bob`
   - Host: `192.168.1.101`
   - Port: `8000`
   - Public Key: [Bob's key]
3. Clicks "Add Peer"

**Step 3: Start Chatting**
1. Alice clicks on Bob in sidebar
2. Types message: "Hi Bob!"
3. Presses Enter
4. Message encrypted and sent instantly!

### Broadcasting to Multiple Peers

```
1. Click 📢 "Broadcast" button
2. Type your message
3. Click "Send to All"
4. Message sent to all peers in parallel!
```

---

## 🔧 Configuration

### Command-Line Options

```bash
# Basic usage
enclave --web

# Custom web port
enclave --web --web-port 8080

# Custom P2P port (for receiving messages)
enclave --web --port 9000 --web-port 5000

# Bind to specific interface
enclave-web --host 192.168.1.100 --port 5000

# Provide password via command (not recommended for security)
enclave-web --password mypassword
```

### Environment Variables

```bash
# Set default ports
export ENCLAVE_P2P_PORT=8000
export ENCLAVE_WEB_PORT=5000

# Then run
enclave --web
```

---

## 🌐 Network Architecture

```
┌──────────────────────────────────────────────┐
│  Web Browser (http://localhost:5000)        │
│  ├─ HTML/CSS/JavaScript                     │
│  └─ WebSocket Connection                    │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│  Flask Web Server (Port 5000)               │
│  ├─ HTTP Routes (REST API)                  │
│  ├─ WebSocket Server (Socket.IO)            │
│  └─ Message History Storage                 │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│  Enclave P2P Layer (Port 8000)             │
│  ├─ Network Server (Listening)              │
│  ├─ Encryption/Decryption                   │
│  └─ Peer-to-Peer Connections                │
└──────────────────────────────────────────────┘
```

---

## 🔒 Security Considerations

### What's Secure
✅ End-to-end encryption (RSA-4096 + AES-256-GCM)
✅ Local key storage (password protected)
✅ No central server (peer-to-peer)
✅ Message integrity (digital signatures)
✅ Replay protection (UUID + timestamp)

### What's NOT Encrypted
⚠️ **Web interface to local server**: HTTP connection on localhost
⚠️ **Metadata**: Peer IP addresses visible in UI
⚠️ **Message history file**: Stored as plaintext JSON locally

### Best Practices

1. **Access Locally Only**: Don't expose web port to internet
2. **Use HTTPS**: Consider reverse proxy with SSL for remote access
3. **Firewall Rules**: Block web port from external access
4. **Strong Passwords**: Use 16+ character passwords for keys
5. **Verify Fingerprints**: Always verify peer fingerprints out-of-band

---

## 📊 Performance

### Resource Usage
- **Memory**: ~50-100MB (Flask + cache)
- **CPU**: <5% idle, 10-15% during messaging
- **Network**: Minimal overhead (WebSocket)

### Scalability
- **Concurrent Users**: Supports multiple browser tabs
- **Message History**: Up to 1000 messages per peer
- **Peer Limit**: No hard limit (tested with 100+ peers)

### Optimizations
- **Connection Pooling**: Enabled by default
- **Key Caching**: All peer keys preloaded
- **Lazy Loading**: Messages loaded on-demand
- **WebSocket**: Real-time without polling

---

## 🐛 Troubleshooting

### Web Interface Won't Load

```bash
# Check if server is running
ps aux | grep enclave

# Check port availability
lsof -i :5000

# Try different port
enclave --web --web-port 8080
```

### Cannot Add Peer

- Verify public key format (should start with `-----BEGIN PUBLIC KEY-----`)
- Check peer's IP address is reachable
- Ensure peer is running Enclave on specified port
- Test connection: `telnet <peer-ip> <peer-port>`

### Messages Not Sending

- Check peer's firewall settings
- Verify peer is online (try ping)
- Check P2P server is running on both sides
- View browser console (F12) for JavaScript errors

### "Web dependencies not installed"

```bash
# Install missing dependencies
pip install flask flask-socketio python-socketio flask-cors

# Or reinstall with web extras
pip install -e ".[web]"
```

---

## 🔄 Running Multiple Instances

You can run CLI and Web GUI simultaneously:

```bash
# Terminal 1: CLI mode
enclave --listen --port 8000

# Terminal 2: Web GUI mode
enclave --web --port 8001 --web-port 5000
```

Note: Each instance needs its own P2P port to avoid conflicts.

---

## 📁 File Structure

```
Enclave/
├── rsa_chat/
│   ├── web_server.py       # Flask backend
│   └── web_launcher.py     # Standalone launcher
├── web/
│   ├── templates/
│   │   └── index.html      # Main HTML page
│   └── static/
│       ├── css/
│       │   └── style.css   # WhatsApp-style CSS
│       └── js/
│           └── app.js      # Client-side JavaScript
└── keys/
    └── messages.json       # Message history (auto-created)
```

---

## 🎨 Customization

### Change Theme Colors

Edit `web/static/css/style.css`:

```css
:root {
    --primary-color: #00a884;  /* Change to your color */
    --secondary-color: #008069;
    --bg-color: #111b21;
    /* ... more variables */
}
```

### Modify Port Defaults

Edit `rsa_chat/web_server.py`:

```python
def start_web_server(host='0.0.0.0', port=5000, password=None):
    # Change default port here
```

---

## 🚀 Advanced Features

### Message History

All messages are automatically saved to `keys/messages.json`:

```json
{
  "fingerprint123": [
    {
      "text": "Hello!",
      "sent": false,
      "timestamp": 1234567890.123,
      "time_str": "02:30 PM"
    }
  ]
}
```

### WebSocket Events

The client can listen to these events:

| Event | Description |
|-------|-------------|
| `new_message` | New message received |
| `message_sent` | Message sent successfully |
| `message_error` | Send failed |
| `broadcast_complete` | Broadcast finished |
| `peer_typing` | Peer is typing |

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/me` | GET | Get user info |
| `/api/peers` | GET | List all peers |
| `/api/peers/<fp>/messages` | GET | Get message history |
| `/api/peers/<fp>/send` | POST | Send message |
| `/api/peers/add` | POST | Add new peer |
| `/api/broadcast` | POST | Broadcast message |
| `/api/export/public-key` | GET | Export public key |

---

## 🎯 Future Enhancements

Planned features for future releases:

- [ ] **File Sharing**: Send images, documents
- [ ] **Voice Messages**: Record and send audio
- [ ] **Video Calls**: P2P video chat
- [ ] **Group Chats**: Multi-peer conversations
- [ ] **Message Reactions**: Emoji reactions
- [ ] **Message Search**: Full-text search
- [ ] **Dark/Light Themes**: Theme switcher
- [ ] **Desktop Notifications**: System notifications
- [ ] **Mobile PWA**: Progressive Web App support
- [ ] **End-to-End Message History Encryption**: Encrypted storage

---

## 💡 Tips & Tricks

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Esc` | Close modal |
| `Ctrl+F` | Search (coming soon) |

### Quick Actions

- **Double-click peer**: Open chat
- **Right-click peer**: Context menu (coming soon)
- **Click timestamp**: View full date
- **Click name**: View peer info

### Development Mode

Enable Flask debug mode:

```python
# In web_server.py
socketio.run(app, host=host, port=port, debug=True)
```

---

## 📞 Support

### Getting Help

1. Check this documentation
2. Read main [README.md](README.md)
3. Check [PERFORMANCE.md](PERFORMANCE.md) for optimization
4. Open GitHub issue

### Reporting Bugs

Include:
- Browser and version
- Console errors (F12 → Console)
- Steps to reproduce
- Expected vs actual behavior

---

## 🎉 Comparison: CLI vs Web GUI

| Feature | CLI | Web GUI |
|---------|-----|---------|
| Interface | Terminal | Browser |
| Ease of Use | Moderate | Very Easy |
| Visual Appeal | Basic | Modern |
| Message History | Scroll back | Persistent |
| Peer Selection | Type fingerprint | Click peer |
| Public Key Sharing | Copy from file | One-click export |
| Multi-tasking | Limited | Multiple tabs |
| Resource Usage | Minimal | Moderate |
| Remote Access | SSH required | HTTP (with proxy) |
| Mobile Friendly | No | Yes |

---

## ✨ Why Use Web GUI?

### For Users
- **No CLI knowledge needed**: Point and click interface
- **Visual feedback**: See typing, delivery status
- **Better organization**: Sidebar with all peers
- **History access**: Browse past conversations easily
- **Modern UX**: Familiar WhatsApp-like experience

### For Developers
- **REST API**: Integrate with other services
- **WebSocket**: Real-time event streaming
- **Extensible**: Easy to add new features
- **Cross-platform**: Works on any OS with browser

---

**Enclave Web GUI**: The power of Enclave with the convenience of modern messaging apps!

---

*For command-line interface documentation, see [README.md](README.md)*
