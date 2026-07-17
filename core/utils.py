from django.utils import timezone

import os
import base64
from cryptography.fernet import Fernet
from django.conf import settings


def evaluate_call_eligibility(application):
    """
    Evaluates enterprise business criteria:
    1. Status must be SHORTLISTED
    2. ATS Match Score must be >= 70.00%
    3. Current local execution time must fall within operational business hours (09:00 - 18:00)
    """
    # 1. Validation Matrix Controls
    if application.status != "SHORTLISTED":
        return False, "Candidate application status is not set to SHORTLISTED."
    
    if application.ats_score < 70.00:
        return False, f"ATS score ({application.ats_score}%) fails to clear the mandatory 70% threshold."

    # 2. Time-Window Validation (Operational Hour Constraints)
    current_time = timezone.localtime(timezone.now())
    current_hour = current_time.hour

    if not (9 <= current_hour < 18):
        return False, f"Outside permissible call window. Current local hour: {current_hour}:00. Blocked until 09:00."

    return True, "All validation boundaries cleared. Profile passed to queue."


class SecureDataCryptographicGuard:
    """
    Day 43 Security Core: Provides deterministic field-level symmetric encryption 
    to protect sensitive candidate identifiers from data leaks.
    """
    @staticmethod
    def get_encryption_cipher():
        # Generates a stable fallback key if a dedicated SECRET_KEY variant is missing from settings
        secret_key = getattr(settings, "SECRET_KEY", "fallback_32_byte_secret_key_string_!!!!")
        # Ensure the key format fits the 32-byte base64 requirement for Fernet
        derived_key = base64.urlsafe_b64encode(secret_key.encode()[:32].ljust(32, b'_'))
        return Fernet(derived_key)

    @classmethod
    def encrypt_field(cls, raw_text: str) -> str:
        if not raw_text:
            return ""
        cipher = cls.get_encryption_cipher()
        return cipher.encrypt(raw_text.encode()).decode()

    @classmethod
    def decrypt_field(cls, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""
        cipher = cls.get_encryption_cipher()
        try:
            return cipher.decrypt(encrypted_text.encode()).decode()
        except Exception:
            return "[DECRYPTION_FAILURE_INTEGRITY_COMPROMISED]"    