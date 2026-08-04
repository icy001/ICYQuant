"""
Verification pipeline.

Orchestrates the signature verification
process from signed payload through
algorithm selection, public key
loading, and signature validation.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..registry import AlgorithmRegistry, AsymmetricAlgorithm
from ..exceptions import CryptoSignatureError


@dataclass
class VerificationResult:
    """
    Verification operation result.

    Attributes:
        valid: Whether the signature is valid.
        algorithm: Algorithm used.
        key_id: Key identifier used.
        reason: Failure reason if invalid.
        metadata: Additional metadata.
    """

    valid: bool = False
    algorithm: str = ""
    key_id: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class VerificationPipeline:
    """
    Verification pipeline orchestrator.

    Manages the verification workflow including:
    - Algorithm selection
    - Public key loading
    - Signature validation
    - Result reporting

    Usage:
        pipeline = VerificationPipeline(registry=registry)
        result = await pipeline.verify(
            data=b"transaction payload",
            signature=sig_result.signature,
            public_key=my_public_key,
        )
    """

    def __init__(self, registry: AlgorithmRegistry) -> None:
        self._registry = registry

    async def verify(
        self,
        data: bytes,
        signature: str,
        public_key: Any,
        algorithm_name: Optional[str] = None,
        key_id: str = "",
        **kwargs: Any,
    ) -> VerificationResult:
        """
        Verify a signature through the pipeline.

        Args:
            data: Original signed data.
            signature: Base64-encoded signature.
            public_key: Public key for verification.
            algorithm_name: Algorithm to use.
            key_id: Key identifier.

        Returns:
            VerificationResult with validity status.
        """
        try:
            algo = self._get_algorithm(algorithm_name)
            sig_bytes = base64.b64decode(signature)

            valid = await algo.verify(
                data=data,
                signature=sig_bytes,
                public_key=public_key,
                **kwargs,
            )

            return VerificationResult(
                valid=valid,
                algorithm=algo.name,
                key_id=key_id,
                reason="" if valid else "Signature verification failed",
                metadata={
                    "data_size": len(data),
                    "signature_size": len(sig_bytes),
                },
            )
        except CryptoSignatureError:
            raise
        except Exception as e:
            return VerificationResult(
                valid=False,
                algorithm=algorithm_name or "unknown",
                reason=str(e),
            )

    def _get_algorithm(
        self,
        name: Optional[str],
    ) -> AsymmetricAlgorithm:
        """Get verification algorithm."""
        if name:
            algo = self._registry.get(name)
            if not isinstance(algo, AsymmetricAlgorithm):
                raise CryptoSignatureError(
                    operation="verify",
                    reason=f"Algorithm {name} does not support verification",
                )
            return algo

        for algo in self._registry._algorithms.values():
            if isinstance(algo, AsymmetricAlgorithm):
                return algo

        raise CryptoSignatureError(
            operation="verify",
            reason="No verification algorithm registered",
        )
