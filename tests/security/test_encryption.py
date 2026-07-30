"""
Tests for ICYQuant Encryption Engine.
"""

import pytest

from services.security.encryption import (
    EncryptionEngine,
    EncryptionAlgorithm,
    FieldEncryption,
    EncryptedField,
    EncryptionError,
)


class TestEncryptionEngine:
    """Test encryption, decryption, and field-level encryption."""

    def setup_method(self):
        self.engine = EncryptionEngine()
        import secrets
        self.key = secrets.token_bytes(32)
        self.engine.set_encryption_key("default", self.key)
        self.engine.register_field(FieldEncryption(
            field_name="account_number",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_name="default",
            searchable=True,
        ))
        self.engine.register_field(FieldEncryption(
            field_name="ssn",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_name="default",
        ))

    def test_encrypt_decrypt_field(self):
        encrypted = self.engine.encrypt_field("account_number", "1234567890")
        assert encrypted.ciphertext != "1234567890"
        plaintext = self.engine.decrypt_field(encrypted)
        assert plaintext == "1234567890"

    def test_encrypt_decrypt_ssn(self):
        encrypted = self.engine.encrypt_field("ssn", "123-45-6789")
        plaintext = self.engine.decrypt_field(encrypted)
        assert plaintext == "123-45-6789"

    def test_encrypt_unregistered_field_raises(self):
        with pytest.raises(EncryptionError):
            self.engine.encrypt_field("nonexistent", "value")

    def test_searchable_encryption(self):
        encrypted = self.engine.encrypt_field("account_number", "1234567890")
        assert encrypted.searchable_hash is not None
        is_valid = self.engine.verify_field("account_number", "1234567890", encrypted)
        assert is_valid is True

    def test_encrypt_record(self):
        record = {"account_number": "1234567890", "name": "Test User"}
        encrypted_record = self.engine.encrypt_record(record)
        assert "account_number" not in encrypted_record
        assert "_account_number_encrypted" in encrypted_record
        assert encrypted_record["name"] == "Test User"

    def test_decrypt_record(self):
        record = {"account_number": "1234567890", "ssn": "123-45-6789"}
        encrypted_record = self.engine.encrypt_record(record)
        decrypted = self.engine.decrypt_record(encrypted_record)
        assert decrypted["account_number"] == "1234567890"
        assert decrypted["ssn"] == "123-45-6789"

    def test_multiple_encryptions_differ(self):
        encrypted1 = self.engine.encrypt_field("account_number", "1234567890")
        encrypted2 = self.engine.encrypt_field("account_number", "1234567890")
        assert encrypted1.ciphertext != encrypted2.ciphertext

    def test_encryption_stats(self):
        self.engine.encrypt_field("account_number", "123")
        self.engine.encrypt_field("account_number", "456")
        stats = self.engine.get_stats()
        assert stats["total_encrypt"] == 2

    def test_list_registered_fields(self):
        fields = self.engine.list_registered_fields()
        assert len(fields) == 2

    def test_get_status(self):
        status = self.engine.to_dict()
        assert status["registeredFields"] == 2
        assert "default" in status["encryptionKeys"]


class TestKeyManagementService:
    """Test KMS operations."""

    def test_create_key(self):
        from services.security.kms import KeyManagementService, KeyType, KeyState
        kms = KeyManagementService()
        key = kms.create_key("test-key", KeyType.AES_256)
        assert key.name == "test-key"
        assert key.state == KeyState.ENABLED

    def test_encrypt_decrypt(self):
        from services.security.kms import KeyManagementService, KeyType
        kms = KeyManagementService()
        kms.create_key("test-key", KeyType.AES_256_GCM)
        ciphertext = kms.encrypt("test-key", "Hello World")
        plaintext = kms.decrypt("test-key", ciphertext)
        assert plaintext == "Hello World"

    def test_rotate_key(self):
        from services.security.kms import KeyManagementService, KeyType, KeyState
        kms = KeyManagementService()
        kms.create_key("test-key", KeyType.AES_256_GCM)
        rotated = kms.rotate_key("test-key")
        assert rotated.state == KeyState.ENABLED
        assert len(rotated.versions) == 1

    def test_list_keys(self):
        from services.security.kms import KeyManagementService, KeyType
        kms = KeyManagementService()
        kms.create_key("key1", KeyType.AES_256)
        kms.create_key("key2", KeyType.AES_256_GCM)
        keys = kms.list_keys()
        assert len(keys) == 2

    def test_delete_key(self):
        from services.security.kms import KeyManagementService, KeyType, KeyState
        kms = KeyManagementService()
        key = kms.create_key("test-key", KeyType.AES_256)
        kms.disable_key("test-key")
        kms.delete_key("test-key")
        key = kms.get_key("test-key")
        assert key is None

    def test_get_status(self):
        from services.security.kms import KeyManagementService, KeyType
        kms = KeyManagementService()
        kms.create_key("key1", KeyType.AES_256)
        status = kms.to_dict()
        assert status["totalKeys"] == 1
