"""
Main entry point for Enclave CLI application.
"""

import sys
import argparse
import getpass
from pathlib import Path
from . import keystore, network, ui

# Import web_server for GUI mode
try:
    from . import web_server
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False


def main():
    """
    Main entry point for Enclave application.
    """
    parser = argparse.ArgumentParser(
        description="Enclave - Secure P2P CLI Messaging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate new key pair
  enclave --generate

  # Start chat server
  enclave --listen --port 8000

  # Add peer's public key
  enclave --add-peer /path/to/peer_key.pem --peer-address 192.168.1.100:8000
        """
    )

    # Arguments
    parser.add_argument('--generate', action='store_true',
                       help='Generate new RSA-4096 key pair')

    parser.add_argument('--listen', action='store_true',
                       help='Start chat server (CLI mode)')

    parser.add_argument('--web', action='store_true',
                       help='Start web GUI (modern WhatsApp-like interface)')

    parser.add_argument('--port', type=int, default=8000,
                       help='Port number for P2P server (default: 8000)')

    parser.add_argument('--web-port', type=int, default=5000,
                       help='Port number for web interface (default: 5000, used with --web)')

    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='IP address to bind server (default: 0.0.0.0)')

    parser.add_argument('--add-peer', type=str, metavar='KEY_PATH',
                       help='Add peer\'s public key')

    parser.add_argument('--peer-address', type=str, metavar='ADDRESS',
                       help='Peer\'s address in format host:port (used with --add-peer)')

    args = parser.parse_args()

    # Validate port range
    if args.port < 1024 or args.port > 65535:
        print("Error: Port must be between 1024 and 65535")
        sys.exit(1)

    try:
        # Handle --generate mode
        if args.generate:
            handle_generate()
            return

        # Handle --add-peer mode
        if args.add_peer:
            if not args.peer_address:
                print("Error: --peer-address required with --add-peer")
                sys.exit(1)
            handle_add_peer(args.add_peer, args.peer_address)
            return

        # Handle --web mode
        if args.web:
            start_web_gui(args.host, args.web_port)
            return

        # Normal chat mode requires --listen
        if not args.listen:
            print("Error: Use --generate to create keys, --add-peer to add peers, --listen for CLI, or --web for GUI")
            parser.print_help()
            sys.exit(1)

        # Start chat mode
        start_chat(args.host, args.port)

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def handle_generate():
    """
    Handle key generation mode.
    """
    print("Generating RSA-4096 key pair...")
    print()

    # Prompt for password
    password = getpass.getpass("Enter password to encrypt private key: ")
    password_confirm = getpass.getpass("Confirm password: ")

    if password != password_confirm:
        print("Error: Passwords do not match")
        sys.exit(1)

    if not password:
        print("Error: Password cannot be empty")
        sys.exit(1)

    # Generate and save keys
    fingerprint = keystore.generate_and_save_keys(password)

    print()
    print("Share this fingerprint with your peers to establish secure communication:")
    print(fingerprint)


def handle_add_peer(key_path: str, peer_address: str):
    """
    Handle adding peer's public key.

    Args:
        key_path: Path to peer's public key file
        peer_address: Peer's address (host:port)
    """
    # Validate address format
    if ':' not in peer_address:
        print("Error: Invalid address format. Use host:port")
        sys.exit(1)

    try:
        host, port_str = peer_address.rsplit(':', 1)
        port = int(port_str)

        if port < 1024 or port > 65535:
            print("Error: Port must be between 1024 and 65535")
            sys.exit(1)

    except ValueError:
        print("Error: Invalid address format. Use host:port")
        sys.exit(1)

    # Add peer key
    try:
        fingerprint = keystore.add_peer_key(key_path)

        # Save peer address
        peers_dir = Path("keys/peers")
        peers_dir.mkdir(parents=True, exist_ok=True)
        address_file = peers_dir / f"{fingerprint}.address"
        address_file.write_text(peer_address)

        print(f"Peer address saved: {host}:{port}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)


def start_chat(host: str, port: int):
    """
    Start chat server and interactive session.

    Args:
        host: IP address to bind
        port: Port number to listen on
    """
    # Prompt for password
    password = getpass.getpass("Enter password to unlock private key: ")

    # Load user's keys
    try:
        private_key, public_key, my_fingerprint = keystore.load_my_keys(password)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Preload all peer keys into cache for maximum performance
    print("Loading peer keys...")
    keystore.preload_all_peer_keys()

    # Load peer addresses from files
    peers = {}
    peers_dir = Path("keys/peers")

    if peers_dir.exists():
        for address_file in peers_dir.glob("*.address"):
            fingerprint = address_file.stem
            address = address_file.read_text().strip()

            # Parse address
            if ':' in address:
                peer_host, peer_port_str = address.rsplit(':', 1)
                try:
                    peer_port = int(peer_port_str)
                    peers[fingerprint] = (peer_host, peer_port)
                except ValueError:
                    print(f"Warning: Invalid address for peer {fingerprint[:12]}: {address}")

    # Create message callback
    message_callback = ui.create_message_callback()

    # Create and start server with optimized settings
    server = network.ChatServer(
        host=host,
        port=port,
        private_key=private_key,
        public_key=public_key,
        fingerprint=my_fingerprint,
        message_callback=message_callback,
        max_workers=20  # ThreadPoolExecutor with 20 workers
    )

    try:
        server.start()

        # Start interactive chat session
        ui.start_chat_session(server, my_fingerprint, private_key, peers)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        server.stop()


def start_web_gui(host: str, web_port: int):
    """
    Start web GUI interface.

    Args:
        host: IP address to bind
        web_port: Port for web interface
    """
    if not WEB_AVAILABLE:
        print("Error: Web dependencies not installed")
        print("Install with: pip install flask flask-socketio flask-cors")
        sys.exit(1)

    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║           Enclave Web GUI - Secure P2P Messaging            ║
    ║                                                               ║
    ║     Modern WhatsApp-like interface with real-time chat       ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    try:
        web_server.start_web_server(host=host, port=web_port)
    except KeyboardInterrupt:
        print("\n\n✓ Web GUI shut down gracefully")


if __name__ == "__main__":
    main()
