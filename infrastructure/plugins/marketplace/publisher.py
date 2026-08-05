"""Publisher management for the plugin marketplace.

Provides :class:`MarketplacePublisher` for managing publisher
identities, key generation, and package signing operations.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MarketplacePublisher:
    """Manages publisher identities, keys, and signing.

    Handles publisher creation, updates, deactivation, keypair
    generation, package signing, and signature verification.

    Usage::

        pub = MarketplacePublisher()
        info = pub.create_publisher("Acme", "acme@example.com")
        pub_key, priv_key = pub.generate_keypair()
        signature = pub.sign_package(pub_id, "/path/to/package.zip")
        valid = pub.verify_package_signature(pkg_path, signature)
    """

    def __init__(self) -> None:
        self._publishers: Dict[str, Dict[str, Any]] = {}
        self._keys: Dict[str, Tuple[str, str]] = {}
        self._create_count: int = 0
        self._sign_count: int = 0
        self._verify_count: int = 0

    def create_publisher(
        self,
        name: str,
        email: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new publisher identity.

        Args:
            name: Publisher display name.
            email: Publisher contact email.
            metadata: Optional additional metadata.

        Returns:
            A dictionary with the created publisher's information.
        """
        import uuid

        publisher_id = uuid.uuid4().hex[:12]
        self._publishers[publisher_id] = {
            "publisher_id": publisher_id,
            "name": name,
            "email": email,
            "metadata": metadata or {},
            "status": "active",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._create_count += 1
        logger.info(
            "Created publisher '%s' (id=%s).", name, publisher_id
        )
        return dict(self._publishers[publisher_id])

    def update_publisher(
        self,
        publisher_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a publisher's information.

        Args:
            publisher_id: Publisher identifier to update.
            updates: Dictionary of fields to update.

        Returns:
            The updated publisher information dictionary.

        Raises:
            KeyError: If the publisher is not found.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        pub = self._publishers[publisher_id]
        for key, value in updates.items():
            if key in ("publisher_id", "created_at"):
                continue
            pub[key] = value
        pub["updated_at"] = time.time()

        logger.info(
            "Updated publisher '%s'.", publisher_id
        )
        return dict(pub)

    def deactivate_publisher(
        self, publisher_id: str
    ) -> Dict[str, Any]:
        """Deactivate a publisher, preventing new package releases.

        Args:
            publisher_id: Publisher identifier to deactivate.

        Returns:
            The updated publisher information.

        Raises:
            KeyError: If the publisher is not found.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        self._publishers[publisher_id]["status"] = "inactive"
        self._publishers[publisher_id]["updated_at"] = time.time()
        logger.info(
            "Deactivated publisher '%s'.", publisher_id
        )
        return dict(self._publishers[publisher_id])

    def activate_publisher(
        self, publisher_id: str
    ) -> Dict[str, Any]:
        """Activate a previously deactivated publisher.

        Args:
            publisher_id: Publisher identifier to activate.

        Returns:
            The updated publisher information.

        Raises:
            KeyError: If the publisher is not found.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        self._publishers[publisher_id]["status"] = "active"
        self._publishers[publisher_id]["updated_at"] = time.time()
        logger.info(
            "Activated publisher '%s'.", publisher_id
        )
        return dict(self._publishers[publisher_id])

    def generate_keypair(self) -> Tuple[str, str]:
        """Generate an RSA keypair for package signing.

        Falls back to an HMAC-based approach if the ``cryptography``
        library is not available.

        Returns:
            A tuple of (public_key_pem, private_key_pem).
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import hashes, serialization

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
            logger.info("Generated RSA keypair.")
            return (public_pem, private_pem)
        except ImportError:
            import base64
            import hashlib

            private_key = base64.b64encode(os.urandom(32)).decode(
                "utf-8"
            )
            public_key = hashlib.sha256(
                private_key.encode("utf-8")
            ).hexdigest()
            logger.info("Generated HMAC keypair (fallback).")
            return (public_key, private_key)

    def sign_package(
        self, publisher_id: str, package_path: str
    ) -> str:
        """Sign a plugin package.

        Args:
            publisher_id: Publisher identifier (must have a
                registered keypair).
            package_path: Filesystem path to the package file.

        Returns:
            A base64-encoded signature string.

        Raises:
            KeyError: If the publisher is not found.
            FileNotFoundError: If the package file does not exist.
        """
        if publisher_id not in self._publishers:
            raise KeyError(
                f"Publisher '{publisher_id}' not found."
            )

        if not os.path.isfile(package_path):
            raise FileNotFoundError(
                f"Package file not found: {package_path}"
            )

        keypair = self._keys.get(publisher_id)
        if keypair is None:
            public_key, private_key = self.generate_keypair()
            self._keys[publisher_id] = (public_key, private_key)
        else:
            _, private_key = keypair

        try:
            with open(package_path, "rb") as f:
                file_data = f.read()

            import base64
            import hashlib
            import hmac

            digest = hashlib.sha256(file_data).digest()

            try:
                from cryptography.hazmat.primitives.asymmetric import padding
                from cryptography.hazmat.primitives import hashes as c_hashes
                from cryptography.hazmat.primitives import serialization

                pk = serialization.load_pem_private_key(
                    private_key.encode("utf-8"), password=None
                )
                signature = pk.sign(
                    digest,
                    padding.PKCS1v15(),
                    c_hashes.SHA256(),
                )
            except (ImportError, Exception):
                signature = hmac.new(
                    private_key.encode("utf-8"),
                    digest,
                    hashlib.sha256,
                ).digest()

            self._sign_count += 1
            signature_b64 = base64.b64encode(signature).decode("utf-8")
            logger.info(
                "Signed package '%s' for publisher '%s'.",
                package_path,
                publisher_id,
            )
            return signature_b64
        except Exception as exc:
            logger.error(
                "Failed to sign package '%s': %s", package_path, exc
            )
            raise

    def verify_package_signature(
        self, package_path: str, signature: str
    ) -> bool:
        """Verify a package's signature.

        Args:
            package_path: Filesystem path to the package file.
            signature: Base64-encoded signature string.

        Returns:
            ``True`` if the signature is valid, ``False`` otherwise.
        """
        if not os.path.isfile(package_path):
            return False

        try:
            import base64
            import hashlib
            import hmac

            with open(package_path, "rb") as f:
                file_data = f.read()

            digest = hashlib.sha256(file_data).digest()
            signature_bytes = base64.b64decode(signature)

            for publisher_id, (pub_key, priv_key) in self._keys.items():
                try:
                    from cryptography.hazmat.primitives.asymmetric import padding
                    from cryptography.hazmat.primitives import hashes as c_hashes
                    from cryptography.hazmat.primitives import serialization

                    pk = serialization.load_pem_public_key(
                        pub_key.encode("utf-8")
                    )
                    pk.verify(
                        signature_bytes,
                        digest,
                        padding.PKCS1v15(),
                        c_hashes.SHA256(),
                    )
                    self._verify_count += 1
                    logger.info(
                        "Verified package '%s' signature.",
                        package_path,
                    )
                    return True
                except Exception:
                    pass

                expected = hmac.new(
                    priv_key.encode("utf-8"),
                    digest,
                    hashlib.sha256,
                ).digest()
                if hmac.compare_digest(expected, signature_bytes):
                    self._verify_count += 1
                    logger.info(
                        "Verified package '%s' signature (HMAC).",
                        package_path,
                    )
                    return True

            logger.warning(
                "Signature verification failed for '%s'.",
                package_path,
            )
            return False
        except Exception as exc:
            logger.error(
                "Error verifying signature for '%s': %s",
                package_path,
                exc,
            )
            return False

    def get_publisher_info(
        self, publisher_id: str
    ) -> Dict[str, Any]:
        """Get detailed publisher information.

        Args:
            publisher_id: Publisher identifier.

        Returns:
            A dictionary with publisher details, or an empty
            dict if not found.
        """
        pub = self._publishers.get(publisher_id)
        if pub is None:
            return {}
        return dict(pub)

    def get_stats(self) -> Dict[str, Any]:
        """Return publisher management statistics.

        Returns:
            Dictionary with publisher counts and operation metrics.
        """
        return {
            "total_publishers": len(self._publishers),
            "active_publishers": sum(
                1
                for p in self._publishers.values()
                if p.get("status") == "active"
            ),
            "keypairs_generated": len(self._keys),
            "create_count": self._create_count,
            "sign_count": self._sign_count,
            "verify_count": self._verify_count,
        }