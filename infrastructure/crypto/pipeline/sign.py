"""
Signing pipeline.

Orchestrates the digital signature
process from payload through hashing,
private key selection, and signature
generation using the appropriate algorithm.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..registry import AlgorithmRegistry, AsymmetricAlgorithm
from ..exceptions import CryptoSignatureError


@dataclass
class SigningResult:
    """
    Signing operation result.

    Attributes:
        signature: Generated signature (base64).
        algorithm: Algorithm used.
        key_id: Key identifier used.
        metadata: Additional metadata.
    """

    signature: str = ""
    algorithm: str = ""
    key_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "metadata": self.metadata,
        }


class SigningPipeline:
    """
    Signing pipeline orchestrator.

    Manages the signing workflow including:
    - Algorithm selection
    - Key loading
    - Payload hashing
    - Signature generation

    Usage:
        pipeline = SigningPipeline(registry=registry)
        result = await pipeline.sign(
            data=b"transaction payload",
            private_key=my_private_key,
        )
    """

    def __init__(self, registry: AlgorithmRegistry) -> None:
        self._registry = registry

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        algorithm_name: Optional[str] = None,
        key_id: str = "",
        **kwargs: Any,
    ) -> SigningResult:
        """
        Sign data through the pipeline.

        Args:
            data: Data to sign.
            private_key: Private key for signing.
            algorithm_name: Algorithm to use.
            key_id: Key identifier.

        Returns:
            SigningResult with generated signature.
        """
        try:
            algo = self._get_algorithm(algorithm_name)

            signature = await algo.sign(
                data=data,
                private_key=private_key,
                **kwargs,
            )

            return SigningResult(
                signature=base64.b64encode(signature).decode(),
                algorithm=algo.name,
                key_id=key_id,
                metadata={
                    "data_size": len(data),
                    "signature_size": len(signature),
                },
            )
        except CryptoSignatureError:
            raise
        except Exception as e:
            raise CryptoSignatureError(
                operation="sign",
                reason=str(e),
            )

    def _get_algorithm(
        self,
        name: Optional[str],
    ) -> AsymmetricAlgorithm:
        """Get signing algorithm."""
        if name:
            algo = self._registry.get(name)
            if not isinstance(algo, AsymmetricAlgorithm):
                raise CryptoSignatureError(
                    operation="sign",
                    reason=f"Algorithm {name} does not support signing",
                )
            return algo

        # Find first asymmetric algorithm
        for algo in self._registry._algorithms.values():
            if isinstance(algo, AsymmetricAlgorithm):
                return algo

        raise CryptoSignatureError(
            operation="sign",
            reason="No signing algorithm registered",
        )
