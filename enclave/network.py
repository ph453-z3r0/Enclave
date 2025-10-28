"""
Networking module for Enclave.
Handles P2P client and server using sockets and threading.
High-performance implementation with ThreadPoolExecutor and connection pooling.
"""

import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from collections import defaultdict
from . import message, keystore


class ChatServer:
    """
    P2P chat server that listens for incoming encrypted messages.
    High-performance with ThreadPoolExecutor and message queue processing.
    """

    def __init__(self, host: str, port: int, private_key, public_key, fingerprint: str, message_callback, max_workers=20):
        """
        Initialize chat server.

        Args:
            host: IP address to bind (default "0.0.0.0")
            port: Port number to listen on
            private_key: User's RSA private key for decryption
            public_key: User's RSA public key
            fingerprint: User's key fingerprint
            message_callback: Function called when message received (signature: callback(sender_fingerprint, plaintext, timestamp))
            max_workers: Maximum number of worker threads (default: 20)
        """
        self.host = host
        self.port = port
        self.private_key = private_key
        self.public_key = public_key
        self.fingerprint = fingerprint
        self.message_callback = message_callback
        self.server_socket = None
        self.running = False

        # ThreadPoolExecutor for handling connections
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ChatServer")

        # Message queue for processing
        self.message_queue = Queue(maxsize=1000)

        # Worker threads for message processing
        self.num_message_workers = 4
        self.message_workers = []

    def start(self):
        """
        Start the chat server and begin accepting connections.
        """
        try:
            # Create TCP socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Set SO_REUSEADDR for quick restart
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Enable TCP_NODELAY for lower latency
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Bind to address
            self.server_socket.bind((self.host, self.port))

            # Listen with larger backlog for high-performance
            self.server_socket.listen(100)

            self.running = True

            # Start message processing worker threads
            for i in range(self.num_message_workers):
                worker = threading.Thread(target=self._message_worker, daemon=True, name=f"MsgWorker-{i}")
                worker.start()
                self.message_workers.append(worker)

            print(f"Listening on {self.host}:{self.port}")
            print(f"Your fingerprint: {self.fingerprint}")
            print(f"Server started with {self.num_message_workers} message workers and ThreadPoolExecutor")

            # Start accept loop in daemon thread
            accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            accept_thread.start()

        except OSError as e:
            if "Address already in use" in str(e):
                print(f"Port {self.port} already in use")
                raise
            else:
                raise

    def _accept_loop(self):
        """
        Accept incoming connections and submit to ThreadPoolExecutor.
        """
        while self.running:
            try:
                # Accept incoming connection
                conn, addr = self.server_socket.accept()

                # Enable TCP_NODELAY for lower latency
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Submit to thread pool for handling
                self.executor.submit(self._handle_client, conn, addr)

            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def _handle_client(self, conn, addr):
        """
        Handle incoming message from a peer.
        Reads message and puts in queue for processing by worker threads.

        Args:
            conn: Socket connection
            addr: Client address tuple
        """
        try:
            # Read 4-byte length prefix (big-endian uint32)
            length_data = self._recv_exact(conn, 4)
            if not length_data:
                return

            message_length = struct.unpack('!I', length_data)[0]

            # Read message data
            message_data = self._recv_exact(conn, message_length)
            if not message_data:
                return

            # Put message in queue for processing (non-blocking)
            try:
                self.message_queue.put((message_data, addr), block=False)
            except:
                # Queue full, drop message
                if self.running:
                    print(f"Message queue full, dropping message from {addr}")

        except Exception as e:
            # Catch all errors and close connection gracefully
            if self.running:
                print(f"Error handling connection: {e}")

        finally:
            # Always close connection
            conn.close()

    def _message_worker(self):
        """
        Worker thread that processes messages from the queue.
        This separates network I/O from crypto operations for better performance.
        """
        while self.running:
            try:
                # Get message from queue with timeout
                message_data, addr = self.message_queue.get(timeout=0.5)

                # Parse message
                envelope = message.parse_message(message_data)

                # Get sender's fingerprint
                sender_fingerprint = envelope['sender_fingerprint']

                # Load sender's public key (with caching)
                try:
                    sender_public_key = keystore.load_peer_key(sender_fingerprint)
                except FileNotFoundError:
                    print(f"Unknown sender: {sender_fingerprint}")
                    continue

                # Check for duplicate (replay protection)
                if message.check_duplicate(envelope['message_id']):
                    # Drop duplicate silently
                    continue

                # Verify and decrypt message
                try:
                    plaintext = message.verify_and_decrypt(envelope, sender_public_key, self.private_key)
                except ValueError as e:
                    print(f"Invalid message from {sender_fingerprint}: {e}")
                    continue

                # Call message callback with decrypted message
                self.message_callback(sender_fingerprint, plaintext, envelope['timestamp'])

            except Empty:
                # No messages in queue, continue
                continue
            except Exception as e:
                if self.running:
                    print(f"Error processing message: {e}")

    def _recv_exact(self, conn, num_bytes):
        """
        Receive exact number of bytes from socket.

        Args:
            conn: Socket connection
            num_bytes: Number of bytes to receive

        Returns:
            Bytes received or None if connection closed
        """
        data = b''
        while len(data) < num_bytes:
            chunk = conn.recv(num_bytes - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def stop(self):
        """
        Stop the chat server.
        """
        self.running = False
        if self.server_socket:
            self.server_socket.close()

        # Shutdown executor gracefully
        self.executor.shutdown(wait=True, cancel_futures=False)

        print("Server stopped")


class ConnectionPool:
    """
    Connection pool for reusing connections to frequently contacted peers.
    Significantly improves performance for repeated messages to same peer.
    """

    def __init__(self, max_connections_per_peer=3, connection_timeout=30):
        """
        Initialize connection pool.

        Args:
            max_connections_per_peer: Maximum cached connections per peer
            connection_timeout: Timeout for idle connections (seconds)
        """
        self.pools = defaultdict(list)
        self.pool_locks = defaultdict(threading.Lock)
        self.max_connections_per_peer = max_connections_per_peer
        self.connection_timeout = connection_timeout
        self.last_used = {}

    def get_connection(self, host, port):
        """
        Get connection from pool or create new one.

        Args:
            host: Target host
            port: Target port

        Returns:
            Socket connection or None
        """
        peer_key = f"{host}:{port}"

        with self.pool_locks[peer_key]:
            # Try to get connection from pool
            while self.pools[peer_key]:
                conn, timestamp = self.pools[peer_key].pop()

                # Check if connection is still valid and not too old
                if time.time() - timestamp < self.connection_timeout:
                    try:
                        # Quick check if connection is alive
                        conn.getpeername()
                        return conn
                    except:
                        # Connection dead, close it
                        try:
                            conn.close()
                        except:
                            pass

        # No valid connection in pool, return None (caller creates new)
        return None

    def return_connection(self, host, port, conn):
        """
        Return connection to pool for reuse.

        Args:
            host: Target host
            port: Target port
            conn: Socket connection
        """
        peer_key = f"{host}:{port}"

        with self.pool_locks[peer_key]:
            # Only keep up to max_connections_per_peer
            if len(self.pools[peer_key]) < self.max_connections_per_peer:
                self.pools[peer_key].append((conn, time.time()))
            else:
                # Pool full, close connection
                try:
                    conn.close()
                except:
                    pass

    def close_all(self):
        """
        Close all pooled connections.
        """
        for peer_key in self.pools:
            with self.pool_locks[peer_key]:
                for conn, _ in self.pools[peer_key]:
                    try:
                        conn.close()
                    except:
                        pass
                self.pools[peer_key].clear()


# Global connection pool for reusing connections
_connection_pool = ConnectionPool()


def send_message(recipient_host: str, recipient_port: int, recipient_fingerprint: str,
                plaintext: str, sender_private_key, sender_fingerprint: str, use_pooling=True):
    """
    Send encrypted message to peer with connection pooling for performance.

    Args:
        recipient_host: Recipient's IP address
        recipient_port: Recipient's port number
        recipient_fingerprint: Recipient's key fingerprint
        plaintext: Message text to send
        sender_private_key: Sender's RSA private key
        sender_fingerprint: Sender's key fingerprint
        use_pooling: Whether to use connection pooling (default: True)

    Returns:
        True if sent successfully

    Raises:
        ConnectionError: If connection or send fails
        ValueError: If recipient key not found
    """
    try:
        # Load recipient's public key (with caching in keystore)
        try:
            recipient_public_key = keystore.load_peer_key(recipient_fingerprint)
        except FileNotFoundError:
            raise ValueError(f"Peer not found: {recipient_fingerprint}")

        # Create encrypted message
        message_data = message.create_message(
            plaintext,
            recipient_public_key,
            sender_private_key,
            sender_fingerprint
        )

        # Try to get connection from pool
        sock = None
        if use_pooling:
            sock = _connection_pool.get_connection(recipient_host, recipient_port)

        # Create new connection if not from pool
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)

            # Enable TCP_NODELAY for lower latency
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Connect to recipient
            sock.connect((recipient_host, recipient_port))

        try:
            # Send 4-byte length prefix (big-endian uint32)
            message_length = len(message_data)
            length_prefix = struct.pack('!I', message_length)
            sock.sendall(length_prefix)

            # Send message data
            sock.sendall(message_data)

            # Return connection to pool for reuse
            if use_pooling:
                _connection_pool.return_connection(recipient_host, recipient_port, sock)
            else:
                sock.close()

            return True

        except:
            # Error during send, close connection
            try:
                sock.close()
            except:
                pass
            raise

    except socket.timeout:
        raise ConnectionError(f"Could not connect to {recipient_host}:{recipient_port}")
    except socket.error as e:
        if "Connection refused" in str(e):
            raise ConnectionError(f"Could not connect to {recipient_host}:{recipient_port}")
        else:
            raise ConnectionError(f"Failed to send message: {e}")


def send_batch_messages(recipients: list, plaintext: str, sender_private_key, sender_fingerprint: str):
    """
    Send same message to multiple recipients in parallel for maximum performance.

    Args:
        recipients: List of (host, port, fingerprint) tuples
        plaintext: Message text to send
        sender_private_key: Sender's RSA private key
        sender_fingerprint: Sender's key fingerprint

    Returns:
        Dictionary mapping recipient fingerprint to success status
    """
    results = {}
    errors = {}

    # Use ThreadPoolExecutor for parallel sends
    with ThreadPoolExecutor(max_workers=min(len(recipients), 10), thread_name_prefix="BatchSend") as executor:
        futures = {}

        # Submit all send operations
        for host, port, fingerprint in recipients:
            future = executor.submit(
                send_message,
                host, port, fingerprint,
                plaintext, sender_private_key, sender_fingerprint
            )
            futures[future] = fingerprint

        # Collect results
        for future in futures:
            fingerprint = futures[future]
            try:
                future.result(timeout=15)
                results[fingerprint] = True
            except Exception as e:
                results[fingerprint] = False
                errors[fingerprint] = str(e)

    return results, errors
