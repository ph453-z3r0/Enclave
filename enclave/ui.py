"""
User interface module for Enclave.
Provides interactive terminal chat interface using prompt_toolkit.
"""

import sys
import threading
from datetime import datetime
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import print_formatted_text
from . import network, keystore


def start_chat_session(server, my_fingerprint: str, sender_private_key, peers: dict):
    """
    Start interactive chat session.

    Args:
        server: Running ChatServer instance
        my_fingerprint: User's key fingerprint
        sender_private_key: User's private key for signing outgoing messages
        peers: Dictionary mapping {fingerprint: (host, port)} for known peers
    """
    # Create prompt session
    session = PromptSession()

    # Print banner
    print("=" * 50)
    print("Enclave v1.0 - Secure P2P Messaging (High-Performance)")
    print(f"Your fingerprint: {my_fingerprint[:12]}...")
    print(f"Connected peers: {len(peers)}")
    print("=" * 50)
    print()
    print("Commands: /send <fingerprint> <message> | /broadcast <message>")
    print("          /peers | /add | /quit")
    print()

    # Main chat loop
    try:
        while True:
            # Get user input
            try:
                user_input = session.prompt("> ")
            except EOFError:
                # Ctrl+D pressed
                _handle_quit(server)
                break
            except KeyboardInterrupt:
                # Ctrl+C pressed
                continue

            # Skip empty input
            if not user_input.strip():
                continue

            # Parse command
            if user_input.startswith('/'):
                _handle_command(user_input, server, my_fingerprint, sender_private_key, peers)
            else:
                print("Unknown command. Use /send, /broadcast, /peers, /add, or /quit")

    except Exception as e:
        print(f"Error in chat session: {e}")
        _handle_quit(server)


def _handle_command(user_input: str, server, my_fingerprint: str, sender_private_key, peers: dict):
    """
    Handle user commands.

    Args:
        user_input: User's input string
        server: ChatServer instance
        my_fingerprint: User's fingerprint
        sender_private_key: User's private key
        peers: Peers dictionary
    """
    parts = user_input.split(maxsplit=2)
    command = parts[0].lower()

    if command == "/quit":
        _handle_quit(server)
        sys.exit(0)

    elif command == "/peers":
        _handle_peers(peers)

    elif command == "/send":
        if len(parts) < 3:
            print("Usage: /send <fingerprint_prefix> <message>")
            return
        fingerprint_prefix = parts[1]
        message_text = parts[2]
        _handle_send(fingerprint_prefix, message_text, peers, sender_private_key, my_fingerprint)

    elif command == "/add":
        _handle_add(peers)

    elif command == "/broadcast":
        if len(parts) < 2:
            print("Usage: /broadcast <message>")
            return
        message_text = user_input[len("/broadcast "):].strip()
        _handle_broadcast(message_text, peers, sender_private_key, my_fingerprint)

    else:
        print("Unknown command. Use /send, /broadcast, /peers, /add, or /quit")


def _handle_send(fingerprint_prefix: str, message_text: str, peers: dict,
                sender_private_key, sender_fingerprint: str):
    """
    Send message to peer.

    Args:
        fingerprint_prefix: Prefix of recipient's fingerprint (min 8 chars)
        message_text: Message to send
        peers: Peers dictionary
        sender_private_key: Sender's private key
        sender_fingerprint: Sender's fingerprint
    """
    # Check minimum prefix length
    if len(fingerprint_prefix) < 8:
        print("Fingerprint prefix must be at least 8 characters")
        return

    # Find matching peer(s)
    matches = []
    for fingerprint, (host, port) in peers.items():
        if fingerprint.startswith(fingerprint_prefix):
            matches.append((fingerprint, host, port))

    if len(matches) == 0:
        print("Peer not found")
        return

    if len(matches) > 1:
        print("Ambiguous fingerprint, be more specific")
        return

    # Get recipient info
    recipient_fingerprint, recipient_host, recipient_port = matches[0]

    # Send message in background thread (non-blocking)
    def send_thread():
        try:
            network.send_message(
                recipient_host,
                recipient_port,
                recipient_fingerprint,
                message_text,
                sender_private_key,
                sender_fingerprint
            )
            print(f"Sent to {recipient_fingerprint[:12]}")
        except Exception as e:
            print(f"Failed to send message: {e}")

    thread = threading.Thread(target=send_thread, daemon=True)
    thread.start()


def _handle_broadcast(message_text: str, peers: dict, sender_private_key, sender_fingerprint: str):
    """
    Broadcast message to all peers in parallel.

    Args:
        message_text: Message to send
        peers: Peers dictionary
        sender_private_key: Sender's private key
        sender_fingerprint: Sender's fingerprint
    """
    if not peers:
        print("No peers configured")
        return

    print(f"Broadcasting to {len(peers)} peer(s)...")

    # Prepare recipient list for batch send
    recipients = [(host, port, fp) for fp, (host, port) in peers.items()]

    # Send in background thread
    def broadcast_thread():
        try:
            results, errors = network.send_batch_messages(
                recipients,
                message_text,
                sender_private_key,
                sender_fingerprint
            )

            # Report results
            success_count = sum(1 for v in results.values() if v)
            print(f"Broadcast complete: {success_count}/{len(peers)} sent successfully")

            # Show errors if any
            if errors:
                for fp, error in errors.items():
                    print(f"  Failed to {fp[:12]}: {error}")

        except Exception as e:
            print(f"Broadcast failed: {e}")

    thread = threading.Thread(target=broadcast_thread, daemon=True)
    thread.start()


def _handle_peers(peers: dict):
    """
    List all known peers.

    Args:
        peers: Peers dictionary
    """
    if not peers:
        print("No peers configured")
        return

    print("Known peers:")
    for fingerprint, (host, port) in peers.items():
        print(f"  {fingerprint[:12]} - {host}:{port}")


def _handle_add(peers: dict):
    """
    Add new peer's public key.

    Args:
        peers: Peers dictionary
    """
    try:
        # Prompt for public key path
        key_path = input("Path to peer's public key file: ").strip()
        if not key_path:
            print("Cancelled")
            return

        # Add peer key
        fingerprint = keystore.add_peer_key(key_path)

        # Prompt for peer address
        address = input("Peer's address (host:port): ").strip()
        if not address:
            print("Cancelled")
            return

        # Parse address
        if ':' not in address:
            print("Invalid address format. Use host:port")
            return

        host, port_str = address.rsplit(':', 1)
        try:
            port = int(port_str)
        except ValueError:
            print("Invalid port number")
            return

        # Add to peers dictionary
        peers[fingerprint] = (host, port)

        # Save peer address to file
        from pathlib import Path
        peers_dir = Path("keys/peers")
        address_file = peers_dir / f"{fingerprint}.address"
        address_file.write_text(address)

        print(f"Peer added: {fingerprint[:12]}")

    except Exception as e:
        print(f"Failed to add peer: {e}")


def _handle_quit(server):
    """
    Quit chat session.

    Args:
        server: ChatServer instance
    """
    print("Goodbye!")
    server.stop()


def create_message_callback():
    """
    Create callback function for incoming messages.

    Returns:
        Callback function that prints incoming messages
    """
    def callback(sender_fingerprint: str, plaintext: str, timestamp: float):
        # Format timestamp
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')

        # Print message
        print(f"[{time_str}] {sender_fingerprint[:12]}: {plaintext}")

    return callback
