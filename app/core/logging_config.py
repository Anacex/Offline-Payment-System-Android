"""
Logging configuration for production monitoring.
Provides structured logging for security events and transactions.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import settings

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
APP_LOG_FILE = LOGS_DIR / "app.log"
SECURITY_LOG_FILE = LOGS_DIR / "security.log"
TRANSACTION_LOG_FILE = LOGS_DIR / "transactions.log"


class SecurityLogger:
    """Logger for security events."""
    
    def __init__(self):
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        handler = RotatingFileHandler(
            SECURITY_LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def log_login_attempt(self, email: str, success: bool, ip_address: str):
        """Log login attempts."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Login {status} - Email: {email} - IP: {ip_address}")
    
    def log_signup(self, email: str, ip_address: str):
        """Log new user signups."""
        self.logger.info(f"New signup - Email: {email} - IP: {ip_address}")
    
    def log_suspicious_activity(self, activity: str, details: str, ip_address: str):
        """Log suspicious activities."""
        self.logger.warning(f"SUSPICIOUS: {activity} - {details} - IP: {ip_address}")
    
    def log_password_change(self, user_id: int, ip_address: str):
        """Log password changes."""
        self.logger.info(f"Password changed - User ID: {user_id} - IP: {ip_address}")
    
    def log_mfa_attempt(self, email: str, success: bool):
        """Log MFA attempts."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"MFA {status} - Email: {email}")


class TransactionLogger:
    """Logger for transaction events."""
    
    def __init__(self):
        self.logger = logging.getLogger("transactions")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        handler = RotatingFileHandler(
            TRANSACTION_LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def log_offline_transaction_created(self, sender_wallet_id: int, amount: float, nonce: str):
        """Log offline transaction creation."""
        self.logger.info(
            f"Offline TX Created - Wallet: {sender_wallet_id} - Amount: {amount} - Nonce: {nonce}"
        )
    
    def log_transaction_synced(self, nonce: str, status: str):
        """Log transaction sync."""
        self.logger.info(f"TX Synced - Nonce: {nonce} - Status: {status}")
    
    def log_transaction_confirmed(self, transaction_id: int, amount: float):
        """Log transaction confirmation."""
        self.logger.info(f"TX Confirmed - ID: {transaction_id} - Amount: {amount}")
    
    def log_wallet_transfer(self, user_id: int, from_wallet: int, to_wallet: int, amount: float):
        """Log wallet transfers."""
        self.logger.info(
            f"Wallet Transfer - User: {user_id} - From: {from_wallet} - To: {to_wallet} - Amount: {amount}"
        )
    
    def log_failed_transaction(self, reason: str, details: str):
        """Log failed transactions."""
        self.logger.warning(f"TX Failed - Reason: {reason} - Details: {details}")


class AppLogger:
    """General application logger."""
    
    def __init__(self):
        self.logger = logging.getLogger("app")
        self.logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(console_handler)
        
        # File handler
        file_handler = RotatingFileHandler(
            APP_LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)


# Initialize loggers
security_logger = SecurityLogger()
transaction_logger = TransactionLogger()
app_logger = AppLogger()
