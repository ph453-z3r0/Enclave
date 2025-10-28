"""
Key management module for Enclave.
Handles local key storage and peer public key management.
High-performance implementation with caching and parallel loading.
"""

import os
import sys
import hashlib
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from . import crypto


# Base directory for key storage
KEYS_DIR = Path("keys")
PRIVATE_KEY_PATH = KEYS_DIR / "my_private_key.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "my_public_key.pem"
PEERS_DIR = KEYS_DIR / "peers"

# Cache for peer public keys (fingerprint -> public_key object)
_peer_key_cache = {}
_cache_lock = threading.Lock()


def generate_and_save_keys(password: str) -> str:
    """
    Generate RSA-4096 key pair and save to disk.

    Args:
        password: Password to encrypt private key

    Returns:
        Fingerprint of generated keys
    """
    # Generate key pair
    private_key_bytes, public_key_bytes, fingerprint = crypto.generate_key_pair(password)

    # Create directories if they don't exist
    KEYS_DIR.mkdir(exist_ok=True)
    PEERS_DIR.mkdir(exist_ok=True)

    # Save private key with restricted permissions
    PRIVATE_KEY_PATH.write_bytes(private_key_bytes)
    os.chmod(PRIVATE_KEY_PATH, 0o600)

    # Save public key
    PUBLIC_KEY_PATH.write_bytes(public_key_bytes)
    os.chmod(PUBLIC_KEY_PATH, 0o644)

    print("Keys generated successfully!")
    print(f"Your fingerprint: {fingerprint}")

    return fingerprint


def load_my_keys(password: str) -> tuple:
    """
    Load user's private and public keys from disk.

    Args:
        password: Password to decrypt private key

    Returns:
        Tuple of (private_key, public_key, fingerprint)
    """
    # Check if keys exist
    if not PRIVATE_KEY_PATH.exists() or not PUBLIC_KEY_PATH.exists():
        print("Keys not found. Run 'enclave --generate' first")
        sys.exit(1)

    # Read key files
    private_key_data = PRIVATE_KEY_PATH.read_bytes()
    public_key_data = PUBLIC_KEY_PATH.read_bytes()

    # Load keys
    private_key = crypto.load_private_key(private_key_data, password)
    public_key = crypto.load_public_key(public_key_data)

    # Calculate fingerprint
    fingerprint = hashlib.sha256(public_key_data).hexdigest()

    return (private_key, public_key, fingerprint)


def add_peer_key(peer_public_key_path: str) -> str:
    """
    Add peer's public key to keystore.

    Args:
        peer_public_key_path: Path to peer's public key file

    Returns:
        Fingerprint of added peer
    """
    # Read peer's public key
    peer_key_path = Path(peer_public_key_path)
    if not peer_key_path.exists():
        raise FileNotFoundError(f"Public key file not found: {peer_public_key_path}")

    public_key_data = peer_key_path.read_bytes()

    # Calculate fingerprint
    fingerprint = hashlib.sha256(public_key_data).hexdigest()

    # Ensure peers directory exists
    PEERS_DIR.mkdir(parents=True, exist_ok=True)

    # Save to peers directory
    peer_key_file = PEERS_DIR / f"{fingerprint}.pem"
    peer_key_file.write_bytes(public_key_data)

    print(f"Peer added: {fingerprint}")

    return fingerprint


def load_peer_key(fingerprint: str):
    """
    Load peer's public key by fingerprint with caching for performance.

    Args:
        fingerprint: SHA-256 fingerprint of peer's public key

    Returns:
        RSA public key object

    Raises:
        FileNotFoundError: If peer key not found
    """
    # Check cache first (read lock not needed for dict reads in Python GIL)
    if fingerprint in _peer_key_cache:
        return _peer_key_cache[fingerprint]

    # Not in cache, load from disk
    peer_key_file = PEERS_DIR / f"{fingerprint}.pem"

    if not peer_key_file.exists():
        raise FileNotFoundError(f"Peer key not found: {fingerprint}")

    public_key_data = peer_key_file.read_bytes()
    public_key = crypto.load_public_key(public_key_data)

    # Add to cache
    with _cache_lock:
        _peer_key_cache[fingerprint] = public_key

    return public_key


def list_peers() -> list:
    """
    List all known peer fingerprints.

    Returns:
        List of fingerprint strings
    """
    if not PEERS_DIR.exists():
        return []

    fingerprints = []
    for pem_file in PEERS_DIR.glob("*.pem"):
        # Extract fingerprint from filename (remove .pem extension)
        fingerprint = pem_file.stem
        fingerprints.append(fingerprint)

    return fingerprints


def preload_all_peer_keys():
    """
    Preload all peer keys into cache in parallel for maximum performance.
    Call this at startup to avoid disk I/O during message processing.

    Returns:
        Number of keys loaded
    """
    fingerprints = list_peers()

    if not fingerprints:
        return 0

    def load_single_key(fingerprint):
        try:
            load_peer_key(fingerprint)
            return True
        except Exception as e:
            print(f"Warning: Failed to load peer key {fingerprint[:12]}: {e}")
            return False

    # Load all keys in parallel
    with ThreadPoolExecutor(max_workers=min(len(fingerprints), 10), thread_name_prefix="KeyLoader") as executor:
        results = list(executor.map(load_single_key, fingerprints))

    loaded = sum(results)
    print(f"Preloaded {loaded}/{len(fingerprints)} peer keys into cache")

    return loaded


def clear_peer_key_cache():
    """
    Clear the peer key cache. Useful for freeing memory or forcing reload.
    """
    with _cache_lock:
        _peer_key_cache.clear()
