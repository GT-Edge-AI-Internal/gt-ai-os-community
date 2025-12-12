"""
Email Service for GT 2.0

SMTP integration using Brevo (formerly Sendinblue) for transactional emails.

Supported email types:
- Budget alert emails (FR #257)
"""

import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional, List
import structlog

logger = structlog.get_logger()


def get_smtp_config() -> dict:
    """Get SMTP configuration from environment"""
    return {
        'host': os.getenv('SMTP_HOST', 'smtp-relay.brevo.com'),
        'port': int(os.getenv('SMTP_PORT', '587')),
        'username': os.getenv('SMTP_USERNAME'),  # Brevo SMTP username (usually your email)
        'password': os.getenv('SMTP_PASSWORD'),  # Brevo SMTP password (from SMTP settings)
        'from_email': os.getenv('SMTP_FROM_EMAIL', 'noreply@gt2.com'),
        'from_name': os.getenv('SMTP_FROM_NAME', 'GT 2.0 Platform'),
        'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    }
