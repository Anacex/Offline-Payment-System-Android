"""
Cryptographic utilities for offline payment system.
Implements RSA asymmetric encryption for secure offline transactions.
"""

import hashlib
import secrets
import json
from datetime import datetime
from typing import Tuple, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class CryptoManager:
    """Manages cryptographic operations for offline transactions."""
    
    KEY_SIZE = 2048  # RSA key size in bits
    
    @staticmethod
    def generate_key_pair() -> Tuple[str, str]:
        """
        Generate RSA key pair for offline wallet.
        
        Returns:
            Tuple of (public_key_pem, private_key_pem) as strings
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=CryptoManager.KEY_SIZE,
            backend=default_backend()
        )
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()  # In production, use BestAvailableEncryption
        ).decode('utf-8')
        
        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return public_pem, private_pem
    
    @staticmethod
    def sign_transaction(transaction_data: Dict[str, Any], private_key_pem: str) -> str:
        """
        Sign transaction data with private key.
        
        Args:
            transaction_data: Dictionary containing transaction details
            private_key_pem: Private key in PEM format
            
        Returns:
            Base64 encoded signature
        """
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Create canonical JSON representation
        message = json.dumps(transaction_data, sort_keys=True).encode('utf-8')
        
        # Sign the message
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Return base64 encoded signature
        import base64
        return base64.b64encode(signature).decode('utf-8')
    
    @staticmethod
    def verify_signature(transaction_data: Dict[str, Any], signature_b64: str, public_key_pem: str) -> bool:
        """
        Verify transaction signature with public key.
        
        Args:
            transaction_data: Dictionary containing transaction details
            signature_b64: Base64 encoded signature
            public_key_pem: Public key in PEM format
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            
            # Decode signature
            import base64
            signature = base64.b64decode(signature_b64)
            
            # Create canonical JSON representation
            message = json.dumps(transaction_data, sort_keys=True).encode('utf-8')
            
            # Verify signature
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False
    
    @staticmethod
    def generate_nonce() -> str:
        """
        Generate a unique nonce for replay attack prevention.
        
        Returns:
            64-character hex string
        """
        return secrets.token_hex(32)
    
    @staticmethod
    def hash_receipt(receipt_data: Dict[str, Any]) -> str:
        """
        Generate SHA-256 hash of receipt data.
        
        Args:
            receipt_data: Dictionary containing receipt information
            
        Returns:
            Hex string of SHA-256 hash
        """
        canonical_json = json.dumps(receipt_data, sort_keys=True)
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    @staticmethod
    def create_payee_qr_payload(payee_id: str, payee_name: str, device_id: str) -> Dict[str, Any]:
        """
        Create Payee QR payload (Step 1 - new MVP format).
        Format: { payeeId, payeeName, deviceId, nonce }
        
        Args:
            payee_id: Payee's unique identifier (e.g., user ID as string)
            payee_name: Payee's display name
            device_id: Device identifier (e.g., device fingerprint)
            
        Returns:
            Dictionary containing Payee QR payload
        """
        return {
            "payeeId": payee_id,
            "payeeName": payee_name,
            "deviceId": device_id,
            "nonce": CryptoManager.generate_nonce()[:16]  # Short nonce for QR
        }
    
    @staticmethod
    def create_qr_payload(public_key: str, user_id: int, wallet_id: int, timestamp: str = None) -> Dict[str, Any]:
        """
        Create QR code payload for receiving offline payments (legacy format).
        DEPRECATED: Use create_payee_qr_payload instead for new MVP flow.
        
        Args:
            public_key: Receiver's public key
            user_id: Receiver's user ID
            wallet_id: Receiver's wallet ID
            timestamp: ISO format timestamp (optional)
            
        Returns:
            Dictionary containing QR payload
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        return {
            "version": "1.0",
            "type": "offline_payment_receiver",
            "public_key": public_key,
            "user_id": user_id,
            "wallet_id": wallet_id,
            "timestamp": timestamp,
            "nonce": CryptoManager.generate_nonce()[:16]  # Short nonce for QR
        }
    
    @staticmethod
    def create_transaction_receipt(
        sender_wallet_id: int,
        receiver_public_key: str,
        amount: float,
        currency: str,
        nonce: str,
        signature: str,
        timestamp: str = None
    ) -> Dict[str, Any]:
        """
        Create a transaction receipt for offline payment.
        
        Args:
            sender_wallet_id: Sender's wallet ID
            receiver_public_key: Receiver's public key
            amount: Transaction amount
            currency: Currency code
            nonce: Transaction nonce
            signature: Transaction signature
            timestamp: ISO format timestamp (optional)
            
        Returns:
            Dictionary containing receipt data
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        receipt = {
            "version": "1.0",
            "type": "offline_payment_receipt",
            "sender_wallet_id": sender_wallet_id,
            "receiver_public_key": receiver_public_key,
            "amount": str(amount),
            "currency": currency,
            "nonce": nonce,
            "signature": signature,
            "timestamp": timestamp
        }
        
        # Add receipt hash
        receipt["receipt_hash"] = CryptoManager.hash_receipt(receipt)
        
        return receipt
    
    @staticmethod
    def encrypt_private_key(private_key_pem: str, password: str) -> str:
        """
        Encrypt private key with password (for secure storage).
        
        Args:
            private_key_pem: Private key in PEM format
            password: Encryption password
            
        Returns:
            Encrypted private key in PEM format
        """
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        # Load the private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Encrypt and serialize
        encrypted_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8'))
        ).decode('utf-8')
        
        return encrypted_pem
    
    @staticmethod
    def decrypt_private_key(encrypted_private_key_pem: str, password: str) -> str:
        """
        Decrypt private key with password.
        
        Args:
            encrypted_private_key_pem: Encrypted private key in PEM format
            password: Decryption password
            
        Returns:
            Decrypted private key in PEM format
        """
        # Load the encrypted private key
        private_key = serialization.load_pem_private_key(
            encrypted_private_key_pem.encode('utf-8'),
            password=password.encode('utf-8'),
            backend=default_backend()
        )
        
        # Serialize without encryption
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        return private_pem
