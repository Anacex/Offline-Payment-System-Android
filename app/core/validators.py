"""
Input validation and sanitization utilities.
Provides additional security beyond Pydantic validation.
"""

import re
from typing import Optional
from fastapi import HTTPException, status


class SecurityValidator:
    """Security-focused input validation."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate Pakistani phone number format."""
        # Pakistani phone: +92 followed by 10 digits
        pattern = r'^\+92[0-9]{10}$'
        return re.match(pattern, phone) is not None
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements.
        Returns (is_valid, error_message)
        """
        if len(password) < 10:
            return False, "Password must be at least 10 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        
        if not re.search(r'[^\w\s]', password):
            return False, "Password must contain at least one special character"
        
        # Check for common weak passwords
        weak_passwords = ['password123', 'admin123', 'qwerty123']
        if password.lower() in weak_passwords:
            return False, "Password is too common. Please choose a stronger password"
        
        return True, None
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 255) -> str:
        """Sanitize string input to prevent injection attacks."""
        if not input_str:
            return ""
        
        # Remove any null bytes
        sanitized = input_str.replace('\x00', '')
        
        # Trim to max length
        sanitized = sanitized[:max_length]
        
        # Remove leading/trailing whitespace
        sanitized = sanitized.strip()
        
        return sanitized
    
    @staticmethod
    def validate_amount(amount: float) -> bool:
        """Validate transaction amount."""
        if amount <= 0:
            return False
        
        # Maximum transaction amount (100 million PKR)
        if amount > 100000000:
            return False
        
        # Check for reasonable decimal places (max 2)
        if round(amount, 2) != amount:
            return False
        
        return True
    
    @staticmethod
    def validate_currency(currency: str) -> bool:
        """Validate currency code."""
        valid_currencies = ['PKR', 'USD', 'AED', 'SAR']
        return currency.upper() in valid_currencies
    
    @staticmethod
    def validate_nonce(nonce: str) -> bool:
        """Validate nonce format (64 hex characters)."""
        if len(nonce) != 64:
            return False
        
        # Check if valid hex string
        try:
            int(nonce, 16)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_wallet_type(wallet_type: str) -> bool:
        """Validate wallet type."""
        valid_types = ['current', 'offline']
        return wallet_type.lower() in valid_types
    
    @staticmethod
    def check_sql_injection(input_str: str) -> bool:
        """
        Check for potential SQL injection patterns.
        Returns True if suspicious patterns found.
        """
        suspicious_patterns = [
            r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b)',
            r'(--|#|/\*|\*/)',
            r'(\bOR\b.*=.*|1=1|\'=\')',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def check_xss(input_str: str) -> bool:
        """
        Check for potential XSS patterns.
        Returns True if suspicious patterns found.
        """
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe',
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return True
        
        return False


def validate_input_security(input_str: str, field_name: str = "input") -> str:
    """
    Comprehensive input validation.
    Raises HTTPException if validation fails.
    """
    if not input_str:
        return input_str
    
    # Check for SQL injection
    if SecurityValidator.check_sql_injection(input_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: suspicious pattern detected"
        )
    
    # Check for XSS
    if SecurityValidator.check_xss(input_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: suspicious pattern detected"
        )
    
    # Sanitize
    return SecurityValidator.sanitize_string(input_str)
