"""
Two-Factor Authentication utilities for GT 2.0

Handles TOTP generation, verification, QR code generation, and secret encryption.
"""
import os
import pyotp
import qrcode
import qrcode.image.pil
import io
import base64
from typing import Optional, Tuple
from cryptography.fernet import Fernet
import structlog

logger = structlog.get_logger()

# Get encryption key from environment
TFA_ENCRYPTION_KEY = os.getenv("TFA_ENCRYPTION_KEY")
TFA_ISSUER_NAME = os.getenv("TFA_ISSUER_NAME", "GT 2.0 Enterprise AI")


class TFAManager:
    """Manager for Two-Factor Authentication operations"""

    def __init__(self):
        if not TFA_ENCRYPTION_KEY:
            raise ValueError("TFA_ENCRYPTION_KEY environment variable must be set")

        # Initialize Fernet cipher for encryption
        self.cipher = Fernet(TFA_ENCRYPTION_KEY.encode())

    def generate_secret(self) -> str:
        """Generate a new TOTP secret (32-byte base32)"""
        secret = pyotp.random_base32()
        logger.info("Generated new TOTP secret")
        return secret

    def encrypt_secret(self, secret: str) -> str:
        """Encrypt TOTP secret using Fernet"""
        try:
            encrypted = self.cipher.encrypt(secret.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Failed to encrypt TFA secret", error=str(e))
            raise

    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt TOTP secret using Fernet"""
        try:
            decrypted = self.cipher.decrypt(encrypted_secret.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Failed to decrypt TFA secret", error=str(e))
            raise

    def generate_qr_code_uri(self, secret: str, email: str, tenant_name: str) -> str:
        """
        Generate otpauth:// URI for QR code scanning

        Args:
            secret: TOTP secret (unencrypted)
            email: User's email address
            tenant_name: Tenant name for issuer branding (required, no fallback)

        Returns:
            otpauth:// URI string
        """
        issuer = f"{tenant_name} - GT AI OS"
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=email, issuer_name=issuer)
        logger.info("Generated QR code URI", email=email, issuer=issuer, tenant_name=tenant_name)
        return uri

    def generate_qr_code_image(self, uri: str) -> str:
        """
        Generate base64-encoded QR code image from URI

        Args:
            uri: otpauth:// URI

        Returns:
            Base64-encoded PNG image data (data:image/png;base64,...)
        """
        try:
            # Create QR code with PIL image factory
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
                image_factory=qrcode.image.pil.PilImage,
            )
            qr.add_data(uri)
            qr.make(fit=True)

            # Create image using PIL
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            logger.error("Failed to generate QR code image", error=str(e))
            raise

    def verify_totp(self, secret: str, code: str, window: int = 1) -> bool:
        """
        Verify TOTP code with time window tolerance

        Args:
            secret: TOTP secret (unencrypted)
            code: 6-digit code from user
            window: Time window tolerance (±30 seconds per window, default=1)

        Returns:
            True if code is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            is_valid = totp.verify(code, valid_window=window)

            if is_valid:
                logger.info("TOTP verification successful")
            else:
                logger.warning("TOTP verification failed")

            return is_valid
        except Exception as e:
            logger.error("TOTP verification error", error=str(e))
            return False

    def get_current_code(self, secret: str) -> str:
        """
        Get current TOTP code (for testing/debugging only)

        Args:
            secret: TOTP secret (unencrypted)

        Returns:
            Current 6-digit TOTP code
        """
        totp = pyotp.TOTP(secret)
        return totp.now()

    def setup_new_tfa(self, email: str, tenant_name: str) -> Tuple[str, str, str]:
        """
        Complete setup for new TFA: generate secret, encrypt, create QR code

        Args:
            email: User's email address
            tenant_name: Tenant name for QR code issuer (required, no fallback)

        Returns:
            Tuple of (encrypted_secret, qr_code_image, manual_entry_key)
        """
        # Generate secret
        secret = self.generate_secret()

        # Encrypt for storage
        encrypted_secret = self.encrypt_secret(secret)

        # Generate QR code URI with tenant branding
        qr_code_uri = self.generate_qr_code_uri(secret, email, tenant_name)

        # Generate QR code image (base64-encoded PNG for display in <img> tag)
        qr_code_image = self.generate_qr_code_image(qr_code_uri)

        # Manual entry key (formatted for easier typing)
        manual_entry_key = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])

        logger.info("TFA setup completed", email=email, tenant_name=tenant_name)

        return encrypted_secret, qr_code_image, manual_entry_key


# Singleton instance
_tfa_manager: Optional[TFAManager] = None


def get_tfa_manager() -> TFAManager:
    """Get singleton TFAManager instance"""
    global _tfa_manager
    if _tfa_manager is None:
        _tfa_manager = TFAManager()
    return _tfa_manager
