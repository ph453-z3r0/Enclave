"""
Cryptographic operations module for Enclave.
Handles RSA-4096 key generation, AES-256-GCM encryption, and digital signatures.
"""

import os
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


def generate_key_pair(password: str) -> tuple:
    """
    Generate RSA-4096 key pair with password protection.

    Args:
        password: Password to encrypt private key

    Returns:
        Tuple of (private_key_bytes, public_key_bytes, fingerprint)
    """
    # Generate RSA-4096 key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    # Get public key
    public_key = private_key.public_key()

    # Serialize private key with password encryption
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8'))
    )

    # Serialize public key (unencrypted)
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Generate fingerprint (SHA-256 of public key)
    fingerprint = hashlib.sha256(public_key_bytes).hexdigest()

    return (private_key_bytes, public_key_bytes, fingerprint)


def load_private_key(key_data: bytes, password: str):
    """
    Load encrypted private key from PEM format.

    Args:
        key_data: PEM-encoded encrypted private key
        password: Password to decrypt private key

    Returns:
        RSA private key object

    Raises:
        ValueError: If password is incorrect
    """
    try:
        private_key = serialization.load_pem_private_key(
            key_data,
            password=password.encode('utf-8'),
            backend=default_backend()
        )
        return private_key
    except Exception:
        raise ValueError("Invalid password")


def load_public_key(key_data: bytes):
    """
    Load public key from PEM format.

    Args:
        key_data: PEM-encoded public key

    Returns:
        RSA public key object
    """
    public_key = serialization.load_pem_public_key(
        key_data,
        backend=default_backend()
    )
    return public_key


def encrypt_message(plaintext: str, recipient_public_key) -> dict:
    """
    Encrypt message using hybrid encryption (AES-256-GCM + RSA-OAEP).

    Args:
        plaintext: Message to encrypt
        recipient_public_key: Recipient's RSA public key

    Returns:
        Dictionary with encrypted_key, ciphertext, nonce, and tag
    """
    # Generate random AES-256 key
    aes_key = os.urandom(32)  # 256 bits

    # Generate random 12-byte nonce for GCM
    nonce = os.urandom(12)

    # Encrypt plaintext with AES-256-GCM
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)

    # AES-GCM ciphertext includes the authentication tag at the end
    # Split ciphertext and tag (tag is last 16 bytes)
    tag = ciphertext[-16:]
    ciphertext_only = ciphertext[:-16]

    # Encrypt AES key with RSA-OAEP
    encrypted_key = recipient_public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return {
        'encrypted_key': encrypted_key,
        'ciphertext': ciphertext_only,
        'nonce': nonce,
        'tag': tag
    }


def decrypt_message(envelope: dict, private_key) -> str:
    """
    Decrypt message using hybrid decryption.

    Args:
        envelope: Dictionary with encrypted_key, ciphertext, nonce, and tag
        private_key: User's RSA private key

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If decryption or integrity check fails
    """
    try:
        # Decrypt AES key with RSA-OAEP
        aes_key = private_key.decrypt(
            envelope['encrypted_key'],
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Reconstruct full ciphertext with tag
        full_ciphertext = envelope['ciphertext'] + envelope['tag']

        # Decrypt with AES-256-GCM (automatically verifies tag)
        aesgcm = AESGCM(aes_key)
        plaintext_bytes = aesgcm.decrypt(envelope['nonce'], full_ciphertext, None)

        return plaintext_bytes.decode('utf-8')

    except Exception as e:
        if 'authentication' in str(e).lower() or 'tag' in str(e).lower():
            raise ValueError("Message integrity check failed")
        else:
            raise ValueError("Decryption failed")


def sign_message(data: bytes, private_key) -> bytes:
    """
    Sign data using RSA-PSS with SHA-256.

    Args:
        data: Data to sign
        private_key: RSA private key

    Returns:
        Signature bytes
    """
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature


def verify_signature(data: bytes, signature: bytes, public_key) -> bool:
    """
    Verify RSA-PSS signature with SHA-256.

    Args:
        data: Original data
        signature: Signature to verify
        public_key: Signer's RSA public key

    Returns:
        True if valid, False if invalid
    """
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
