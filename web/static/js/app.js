// Enclave Web GUI - Client-side JavaScript
// Modern WhatsApp-like interface with real-time messaging

// Global state
let socket = null;
let currentPeer = null;
let peers = [];
let myInfo = null;
let typingTimeout = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize WebSocket
    initWebSocket();

    // Load initial data
    loadMyInfo();
    loadPeers();

    // Setup event listeners
    setupEventListeners();
}

// WebSocket Connection
function initWebSocket() {
    socket = io();

    socket.on('connect', function() {
        console.log('Connected to server');
        showToast('Connected to Enclave server', 'success');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        showToast('Disconnected from server', 'error');
    });

    socket.on('new_message', function(data) {
        handleNewMessage(data);
    });

    socket.on('message_sent', function(data) {
        console.log('Message sent:', data);
    });

    socket.on('message_error', function(data) {
        showToast('Failed to send message: ' + data.error, 'error');
    });

    socket.on('broadcast_complete', function(data) {
        showToast(`Broadcast complete: ${data.success_count}/${data.total} sent`, 'success');
        closeModal('broadcast-modal');
    });

    socket.on('peer_typing', function(data) {
        if (data.peer === currentPeer) {
            showTypingIndicator();
        }
    });
}

// API Calls
async function loadMyInfo() {
    try {
        const response = await fetch('/api/me');
        const data = await response.json();
        myInfo = data;

        document.getElementById('my-fingerprint').textContent = data.short_fingerprint || 'Loading...';
    } catch (error) {
        console.error('Failed to load my info:', error);
    }
}

async function loadPeers() {
    try {
        const response = await fetch('/api/peers');
        const data = await response.json();
        peers = data.peers;

        renderPeers();
    } catch (error) {
        console.error('Failed to load peers:', error);
    }
}

async function loadMessages(fingerprint) {
    try {
        const response = await fetch(`/api/peers/${fingerprint}/messages`);
        const data = await response.json();

        renderMessages(data.messages);
    } catch (error) {
        console.error('Failed to load messages:', error);
    }
}

// Rendering Functions
function renderPeers() {
    const peersList = document.getElementById('peers-list');

    if (peers.length === 0) {
        peersList.innerHTML = `
            <div class="no-peers">
                <i class="fas fa-user-friends"></i>
                <p>No peers yet</p>
                <button class="btn-primary" onclick="showAddPeerModal()">Add Your First Peer</button>
            </div>
        `;
        return;
    }

    peersList.innerHTML = peers.map(peer => `
        <div class="peer-item ${currentPeer === peer.fingerprint ? 'active' : ''}"
             onclick="selectPeer('${peer.fingerprint}')">
            <div class="avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="peer-details">
                <div class="peer-header">
                    <span class="peer-name">${escapeHtml(peer.name)}</span>
                    ${peer.unread > 0 ? `<span class="unread-badge">${peer.unread}</span>` : ''}
                </div>
                <div class="peer-preview">
                    ${peer.short_fingerprint} • ${peer.host}:${peer.port}
                </div>
            </div>
        </div>
    `).join('');
}

function renderMessages(messages) {
    const container = document.getElementById('messages-container');

    if (messages.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                <i class="fas fa-comments" style="font-size: 48px; margin-bottom: 15px; opacity: 0.5;"></i>
                <p>No messages yet. Start the conversation!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = messages.map(msg => `
        <div class="message ${msg.sent ? 'sent' : 'received'}">
            <div class="message-content">
                <div class="message-text">${escapeHtml(msg.text).replace(/\n/g, '<br>')}</div>
                <div class="message-time">${msg.time_str}</div>
            </div>
        </div>
    `).join('');

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Peer Selection
function selectPeer(fingerprint) {
    currentPeer = fingerprint;

    const peer = peers.find(p => p.fingerprint === fingerprint);
    if (!peer) return;

    // Update UI
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('chat-container').style.display = 'flex';

    document.getElementById('current-peer-name').textContent = peer.name;
    document.getElementById('current-peer-status').textContent = `${peer.host}:${peer.port}`;

    // Update active peer in sidebar
    renderPeers();

    // Load messages
    loadMessages(fingerprint);
}

// Message Handling
function handleNewMessage(data) {
    // Add to UI if chat is open
    if (currentPeer === data.from) {
        const container = document.getElementById('messages-container');
        const messageHtml = `
            <div class="message received">
                <div class="message-content">
                    <div class="message-text">${escapeHtml(data.text).replace(/\n/g, '<br>')}</div>
                    <div class="message-time">${data.time_str}</div>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', messageHtml);
        container.scrollTop = container.scrollHeight;
    }

    // Show notification
    const peer = peers.find(p => p.fingerprint === data.from);
    const peerName = peer ? peer.name : data.from.substring(0, 12);

    showToast(`New message from ${peerName}`, 'info');

    // Play notification sound (optional)
    playNotificationSound();
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();

    if (!message || !currentPeer) return;

    try {
        const response = await fetch(`/api/peers/${currentPeer}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (response.ok) {
            // Add to UI immediately
            const container = document.getElementById('messages-container');
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });

            const messageHtml = `
                <div class="message sent">
                    <div class="message-content">
                        <div class="message-text">${escapeHtml(message).replace(/\n/g, '<br>')}</div>
                        <div class="message-time">${timeStr}</div>
                    </div>
                </div>
            `;

            container.insertAdjacentHTML('beforeend', messageHtml);
            container.scrollTop = container.scrollHeight;

            // Clear input
            input.value = '';
        } else {
            showToast('Failed to send message', 'error');
        }
    } catch (error) {
        console.error('Send error:', error);
        showToast('Failed to send message', 'error');
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function handleTyping() {
    if (!currentPeer) return;

    // Emit typing event
    socket.emit('typing', { peer: currentPeer });

    // Clear previous timeout
    if (typingTimeout) clearTimeout(typingTimeout);

    // Set new timeout
    typingTimeout = setTimeout(() => {
        // User stopped typing
    }, 1000);
}

function showTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    indicator.style.display = 'flex';

    setTimeout(() => {
        indicator.style.display = 'none';
    }, 3000);
}

// Modals
function showAddPeerModal() {
    document.getElementById('add-peer-modal').classList.add('active');
}

function showMyKeyModal() {
    fetch('/api/export/public-key')
        .then(response => response.json())
        .then(data => {
            document.getElementById('my-public-key').value = data.public_key;
            document.getElementById('my-full-fingerprint').value = data.fingerprint;
            document.getElementById('my-key-modal').classList.add('active');
        })
        .catch(error => {
            showToast('Failed to load public key', 'error');
        });
}

function showBroadcastModal() {
    document.getElementById('peer-count').textContent = peers.length;
    document.getElementById('broadcast-modal').classList.add('active');
}

function showPeerInfo() {
    if (!currentPeer) return;

    const peer = peers.find(p => p.fingerprint === currentPeer);
    if (!peer) return;

    document.getElementById('info-peer-name').textContent = peer.name;
    document.getElementById('info-peer-fingerprint').textContent = peer.fingerprint;
    document.getElementById('info-peer-address').textContent = `${peer.host}:${peer.port}`;
    document.getElementById('info-peer-status').textContent = peer.online ? 'Online' : 'Offline';

    document.getElementById('peer-info-modal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Add Peer
async function addPeer() {
    const name = document.getElementById('peer-name').value.trim();
    const host = document.getElementById('peer-host').value.trim();
    const port = document.getElementById('peer-port').value.trim();
    const publicKey = document.getElementById('peer-public-key').value.trim();

    if (!host || !port || !publicKey) {
        showToast('Please fill all required fields', 'error');
        return;
    }

    try {
        const response = await fetch('/api/peers/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name || 'New Peer',
                host,
                port: parseInt(port),
                public_key: publicKey
            })
        });

        const data = await response.json();

        if (response.ok) {
            showToast('Peer added successfully!', 'success');
            closeModal('add-peer-modal');

            // Clear form
            document.getElementById('peer-name').value = '';
            document.getElementById('peer-host').value = '';
            document.getElementById('peer-port').value = '8000';
            document.getElementById('peer-public-key').value = '';

            // Reload peers
            await loadPeers();
        } else {
            showToast('Failed to add peer: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Add peer error:', error);
        showToast('Failed to add peer', 'error');
    }
}

// Broadcast
async function broadcastMessage() {
    const message = document.getElementById('broadcast-message').value.trim();

    if (!message) {
        showToast('Please enter a message', 'error');
        return;
    }

    try {
        const response = await fetch('/api/broadcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (response.ok) {
            document.getElementById('broadcast-message').value = '';
            showToast('Broadcasting message...', 'info');
        } else {
            showToast('Failed to broadcast', 'error');
        }
    } catch (error) {
        console.error('Broadcast error:', error);
        showToast('Failed to broadcast', 'error');
    }
}

// Utility Functions
function copyPublicKey() {
    const textarea = document.getElementById('my-public-key');
    textarea.select();
    document.execCommand('copy');
    showToast('Public key copied to clipboard', 'success');
}

function downloadPublicKey() {
    const publicKey = document.getElementById('my-public-key').value;
    const blob = new Blob([publicKey], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'my_public_key.pem';
    a.click();
    URL.revokeObjectURL(url);
    showToast('Public key downloaded', 'success');
}

function filterPeers() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const peerItems = document.querySelectorAll('.peer-item');

    peerItems.forEach(item => {
        const peerName = item.querySelector('.peer-name').textContent.toLowerCase();
        const peerPreview = item.querySelector('.peer-preview').textContent.toLowerCase();

        if (peerName.includes(searchTerm) || peerPreview.includes(searchTerm)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? 'check-circle' :
                 type === 'error' ? 'exclamation-circle' :
                 'info-circle';

    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function playNotificationSound() {
    // Simple beep using Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
        console.log('Could not play notification sound');
    }
}

// Additional features
function searchInChat() {
    showToast('Search feature coming soon', 'info');
}

function showEmojiPicker() {
    showToast('Emoji picker coming soon', 'info');
}

function attachFile() {
    showToast('File sharing feature coming soon', 'info');
}

function setupEventListeners() {
    // Close modals when clicking outside
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('active');
            }
        });
    });

    // ESC key to close modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });
}

// Auto-refresh peers every 30 seconds
setInterval(() => {
    loadPeers();
}, 30000);
