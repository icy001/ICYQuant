"""
Snapshot compressor.
"""

import json
import zlib


class SnapshotCompressor:

    def compress(
        self,
        snapshot,
    ):

        payload = json.dumps(
            snapshot
        ).encode()

        return zlib.compress(
            payload
        )

    def decompress(
        self,
        payload,
    ):

        return json.loads(
            zlib.decompress(
                payload
            ).decode()
        )