"""
Worker process.

Responsibilities:

- replay jobs
- reconciliation jobs
- snapshot jobs
"""

from __future__ import annotations

import time


def main():
    print(
        "ICYQuant worker started"
    )

    while True:
        # placeholder
        # future:
        # consume Redis queue
        # execute jobs

        time.sleep(10)


if __name__ == "__main__":
    main()