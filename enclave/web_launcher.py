#!/usr/bin/env python3
"""
Standalone launcher for Enclave Web GUI.
"""

import sys
import argparse
from . import web_server


def main():
    parser = argparse.ArgumentParser(
        description='Enclave Web GUI - Modern WhatsApp-like Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start web GUI on default port (5000)
  enclave-web

  # Start on custom port
  enclave-web --port 8080

  # Bind to specific interface
  enclave-web --host 192.168.1.100 --port 5000
        """
    )

    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Host to bind web server (default: 0.0.0.0)')

    parser.add_argument('--port', type=int, default=5000,
                       help='Port for web interface (default: 5000)')

    parser.add_argument('--password', type=str, default=None,
                       help='Password to unlock keys (will prompt if not provided)')

    args = parser.parse_args()

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
        web_server.start_web_server(
            host=args.host,
            port=args.port,
            password=args.password
        )
    except KeyboardInterrupt:
        print("\n\n✓ Web GUI shut down gracefully")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
