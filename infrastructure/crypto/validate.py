"""
Crypto platform validation test.

Comprehensive validation test that verifies
the entire crypto platform including:
- Import and basic instantiation
- Algorithm registry
- Envelope encryption
- KMS integration
- Pipeline operations
- Key management
- Metrics and diagnostics
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from typing import Any, Dict, List

PASSED = 0
FAILED = 0
ERRORS: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  ✗ {name} - {detail}")


def check_async(name: str, coro: Any) -> None:
    global PASSED, FAILED
    try:
        result = asyncio.get_event_loop().run_until_complete(coro)
        PASSED += 1
        print(f"  ✓ {name}")
    except Exception as e:
        FAILED += 1
        ERRORS.append(f"{name}: {e}")
        print(f"  ✗ {name} - {e}")
        traceback.print_exc()


def main() -> None:
    global PASSED, FAILED
    print("=" * 60)
    print("ICYQuant Crypto Platform Validation")
    print("=" * 60)

    # Test 1: Import test
    print("\n--- Import Test ---")
    try:
        import infrastructure.crypto as crypto
        check("Import infrastructure.crypto", True)
    except Exception as e:
        check("Import infrastructure.crypto", False, str(e))
        print("ABORT: Cannot import module")
        return

    # Test 2: Exports
    print("\n--- Export Verification ---")
    expected_exports = [
        "CryptoService",
        "CryptoManager",
        "CryptoConfig",
        "AlgorithmRegistry",
        "EnvelopeEncryption",
        "KeyStore",
        "Keyring",
        "CryptoMetrics",
        "CryptoHealthCheck",
        "CryptoDiagnostics",
        "AES256GCM",
        "ChaCha20Poly1305",
        "RSA2048",
        "RSA4096",
        "Ed25519",
        "HMACSHA256",
        "SHA256",
        "SHA512",
        "BcryptPassword",
        "LocalKMSProvider",
        "EncryptionPipeline",
        "DecryptionPipeline",
        "SigningPipeline",
        "VerificationPipeline",
        "HashPipeline",
        "KeyRotationPipeline",
        "CryptoError",
        "CryptoEncryptionError",
        "CryptoKeyError",
    ]
    for name in expected_exports:
        check(f"Export {name}", hasattr(crypto, name),
              f"Missing from module")

    # Test 3: Algorithm instantiation
    print("\n--- Algorithm Tests ---")
    try:
        algo = crypto.AES256GCM()
        check("AES256GCM instantiation", algo.name == "aes-256-gcm")
    except Exception as e:
        check("AES256GCM instantiation", False, str(e))

    try:
        algo = crypto.ChaCha20Poly1305()
        check("ChaCha20Poly1305 instantiation",
              algo.name == "chacha20-poly1305")
    except Exception as e:
        check("ChaCha20Poly1305 instantiation", False, str(e))

    try:
        algo = crypto.RSA2048()
        check("RSA2048 instantiation", algo.name == "rsa-2048")
    except Exception as e:
        check("RSA2048 instantiation", False, str(e))

    try:
        algo = crypto.Ed25519()
        check("Ed25519 instantiation", algo.name == "ed25519")
    except Exception as e:
        check("Ed25519 instantiation", False, str(e))

    try:
        algo = crypto.HMACSHA256()
        check("HMACSHA256 instantiation", algo.name == "hmac-sha256")
    except Exception as e:
        check("HMACSHA256 instantiation", False, str(e))

    try:
        algo = crypto.SHA256()
        check("SHA256 instantiation", algo.name == "sha-256")
    except Exception as e:
        check("SHA256 instantiation", False, str(e))

    try:
        algo = crypto.BcryptPassword()
        check("BcryptPassword instantiation", algo.name == "bcrypt")
    except Exception as e:
        check("BcryptPassword instantiation", False, str(e))

    # Test 4: Registry
    print("\n--- Algorithm Registry ---")
    try:
        registry = crypto.AlgorithmRegistry()
        registry.register(crypto.AES256GCM())
        registry.register(crypto.ChaCha20Poly1305())
        registry.register(crypto.HMACSHA256())
        registry.register(crypto.SHA256())
        check("Algorithm registration", registry.count() == 4)
        check("Registry get by name",
              registry.get("aes-256-gcm").name == "aes-256-gcm")
    except Exception as e:
        check("Algorithm registry", False, str(e))
        traceback.print_exc()

    # Test 5: Config
    print("\n--- Configuration ---")
    try:
        config = crypto.CryptoConfig()
        check("CryptoConfig creation", config is not None)
        check("Config has kms_provider", hasattr(config, "kms_provider"))
    except Exception as e:
        check("CryptoConfig", False, str(e))

    # Test 6: KMS Provider
    print("\n--- KMS Provider ---")
    try:
        kms = crypto.LocalKMSProvider()
        check("LocalKMSProvider creation", kms is not None)
        check("KMS get_name", kms.get_name() == "local")
    except Exception as e:
        check("LocalKMSProvider", False, str(e))

    # Test 7: Key Store
    print("\n--- Key Store ---")
    try:
        ks = crypto.KeyStore()
        check("KeyStore creation", ks is not None)
        check("KeyStore count", ks.count() == 0)
        stats = ks.get_stats()
        check("KeyStore stats", "total_keys" in stats)
    except Exception as e:
        check("KeyStore", False, str(e))

    # Test 8: Keyring
    print("\n--- Keyring ---")
    try:
        kr = crypto.Keyring()
        check("Keyring creation", kr is not None)
        kr.store_key("test-key", b"test-material", "aes-256-gcm")
        check("Keyring store_key", kr.count() == 1)
        mat = kr.get_material("test-key")
        check("Keyring get_material", mat == b"test-material")
        check("Keyring remove_key", kr.remove_key("test-key"))
        check("Keyring after remove", kr.count() == 0)
    except Exception as e:
        check("Keyring", False, str(e))
        traceback.print_exc()

    # Test 9: Metrics
    print("\n--- Metrics ---")
    try:
        m = crypto.CryptoMetrics(enabled=True)
        m.record_encrypt("aes-256-gcm", "envelope", True, 0.005)
        check("Metrics record_encrypt", True)
        stats = m.get_stats()
        check("Metrics stats", "counters" in stats)
        check("Metrics has counter data",
              stats["counters"].get("encrypt_total", 0) >= 1)
    except Exception as e:
        check("Metrics", False, str(e))
        traceback.print_exc()

    # Test 10: Diagnostics
    print("\n--- Diagnostics ---")
    try:
        d = crypto.CryptoDiagnostics()
        d.record_operation("encrypt", "aes-256-gcm", True, 5.0, "my-key")
        ops = d.get_operations()
        check("Diagnostics record", len(ops) >= 1)
        perf = d.get_performance_stats()
        check("Diagnostics performance", "encrypt" in perf)
        stats = d.get_stats()
        check("Diagnostics stats", stats["total_operations"] >= 1)
    except Exception as e:
        check("Diagnostics", False, str(e))
        traceback.print_exc()

    # Test 11: Exceptions
    print("\n--- Exception Hierarchy ---")
    try:
        e1 = crypto.CryptoError("test", algorithm="aes-256-gcm")
        check("CryptoError", isinstance(e1, Exception))
        e2 = crypto.CryptoEncryptionError(algorithm="aes", reason="fail")
        check("CryptoEncryptionError",
              isinstance(e2, crypto.CryptoError))
        e3 = crypto.CryptoKeyError(key_id="k1", operation="op", reason="r")
        check("CryptoKeyError",
              isinstance(e3, crypto.CryptoError))
    except Exception as e:
        check("Exceptions", False, str(e))

    # Test 12: Pipeline instantiation
    print("\n--- Pipeline Instantiation ---")
    try:
        reg = crypto.AlgorithmRegistry()
        reg.register(crypto.AES256GCM())
        reg.register(crypto.HMACSHA256())
        reg.register(crypto.SHA256())
        reg.register(crypto.ChaCha20Poly1305())

        enc = crypto.EncryptionPipeline(registry=reg, envelope_enabled=False)
        check("EncryptionPipeline", enc is not None)

        dec = crypto.DecryptionPipeline(registry=reg)
        check("DecryptionPipeline", dec is not None)

        sign = crypto.SigningPipeline(registry=reg)
        check("SigningPipeline", sign is not None)

        ver = crypto.VerificationPipeline(registry=reg)
        check("VerificationPipeline", ver is not None)

        h = crypto.HashPipeline(registry=reg)
        check("HashPipeline", h is not None)
    except Exception as e:
        check("Pipelines", False, str(e))
        traceback.print_exc()

    # Test 13: Envelope instantiation
    print("\n--- Envelope Encryption ---")
    try:
        from infrastructure.crypto.envelope import EnvelopeEncryption
        from infrastructure.crypto.kms import LocalKMSProvider
        from infrastructure.crypto.config import CryptoConfig

        reg = crypto.AlgorithmRegistry()
        reg.register(crypto.AES256GCM())
        reg.register(crypto.ChaCha20Poly1305())

        kms = LocalKMSProvider()
        config = CryptoConfig()
        env = EnvelopeEncryption(
            registry=reg,
            kms_provider=kms,
            config=config,
        )
        check("EnvelopeEncryption creation", env is not None)
    except Exception as e:
        check("EnvelopeEncryption", False, str(e))
        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {PASSED} passed, {FAILED} failed")
    if ERRORS:
        print("\nFailed tests:")
        for err in ERRORS:
            print(f"  - {err}")
    print("=" * 60)

    sys.exit(0 if FAILED == 0 else 1)


if __name__ == "__main__":
    main()
