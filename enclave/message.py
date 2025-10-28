"""
Message protocol module for Enclave.
Handles message structure, serialization, and replay protection.
"""

import time
import uuid
import msgpack
import threading
from collections import deque
from . import crypto


# Message ID deque for duplicate detection (thread-safe)
_seen_message_ids = deque(maxlen=10000)
_seen_ids_lock = threading.Lock()


def create_message(plaintext: str, recipient_public_key, sender_private_key, sender_fingerprint: str) -> bytes:
    """
    Create encrypted and signed message envelope.

    Args:
        plaintext: Message text to send
        recipient_public_key: Recipient's RSA public key
        sender_private_key: Sender's RSA private key
        sender_fingerprint: Sender's key fingerprint

    Returns:
        Serialized message bytes

    Raises:
        ValueError: If plaintext exceeds 10,000 characters
    """
    # Check message size limit
    if len(plaintext) > 10000:
        raise ValueError("Message too large (max 10,000 chars)")

    # Generate unique message ID
    message_id = str(uuid.uuid4())

    # Get current timestamp
    timestamp = time.time()

    # Encrypt message using hybrid encryption
    encrypted_components = crypto.encrypt_message(plaintext, recipient_public_key)

    # Build envelope (without signature)
    envelope = {
        'version': 1,
        'message_id': message_id,
        'timestamp': timestamp,
        'sender_fingerprint': sender_fingerprint,
        'encrypted_key': encrypted_components['encrypted_key'],
        'ciphertext': encrypted_components['ciphertext'],
        'nonce': encrypted_components['nonce'],
        'tag': encrypted_components['tag']
    }

    # Serialize envelope for signing
    envelope_bytes = msgpack.packb(envelope, use_bin_type=True)

    # Sign the serialized envelope
    signature = crypto.sign_message(envelope_bytes, sender_private_key)

    # Add signature to envelope
    envelope['signature'] = signature

    # Serialize final envelope with signature
    final_envelope_bytes = msgpack.packb(envelope, use_bin_type=True)

    return final_envelope_bytes


def parse_message(data: bytes) -> dict:
    """
    Parse and validate message envelope.

    Args:
        data: Serialized message bytes

    Returns:
        Envelope dictionary

    Raises:
        ValueError: If message format is invalid
    """
    try:
        # Deserialize message
        envelope = msgpack.unpackb(data, raw=False)

        # Validate required fields
        required_fields = ['version', 'message_id', 'timestamp', 'sender_fingerprint',
                          'encrypted_key', 'ciphertext', 'nonce', 'tag', 'signature']

        for field in required_fields:
            if field not in envelope:
                raise ValueError(f"Missing required field: {field}")

        # Validate protocol version
        if envelope['version'] != 1:
            raise ValueError(f"Unsupported protocol version: {envelope['version']}")

        return envelope

    except Exception as e:
        raise ValueError(f"Invalid message format: {str(e)}")


def verify_and_decrypt(envelope: dict, sender_public_key, my_private_key) -> str:
    """
    Verify signature, check timestamp, and decrypt message.

    Args:
        envelope: Parsed message envelope
        sender_public_key: Sender's RSA public key
        my_private_key: Recipient's RSA private key

    Returns:
        Decrypted plaintext message

    Raises:
        ValueError: If verification or decryption fails
    """
    # Extract signature
    signature = envelope['signature']

    # Create envelope copy without signature for verification
    envelope_copy = envelope.copy()
    del envelope_copy['signature']

    # Serialize envelope for signature verification
    envelope_bytes = msgpack.packb(envelope_copy, use_bin_type=True)

    # Verify signature
    if not crypto.verify_signature(envelope_bytes, signature, sender_public_key):
        raise ValueError("Invalid signature")

    # Check timestamp (must be within 5 minutes of current time)
    current_time = time.time()
    message_time = envelope['timestamp']

    if message_time > current_time + 300:
        raise ValueError("Message timestamp too far in future")

    if message_time < current_time - 300:
        raise ValueError("Message timestamp too old")

    # Decrypt message
    decryption_envelope = {
        'encrypted_key': envelope['encrypted_key'],
        'ciphertext': envelope['ciphertext'],
        'nonce': envelope['nonce'],
        'tag': envelope['tag']
    }

    plaintext = crypto.decrypt_message(decryption_envelope, my_private_key)

    return plaintext


def check_duplicate(message_id: str) -> bool:
    """
    Check if message ID has been seen before (replay protection).

    Args:
        message_id: UUID string of message

    Returns:
        True if duplicate (already seen), False if new
    """
    with _seen_ids_lock:
        if message_id in _seen_message_ids:
            return True

        # Add to seen set
        _seen_message_ids.append(message_id)
        return False
