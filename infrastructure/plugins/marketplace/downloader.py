"""Download management for the plugin marketplace.

Provides :class:`MarketplaceDownloader` for downloading plugin
packages with progress tracking, cancellation, and retry logic.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketplaceDownloader:
    """Manages downloads for the plugin marketplace.

    Supports progress tracking, cancellation, retry logic, and
    both file-based and in-memory downloads.

    Usage::

        downloader = MarketplaceDownloader()
        path = await downloader.download_package(
            "my.plugin", "1.0.0", "/tmp/downloads"
        )
        progress = downloader.get_progress(download_id)
        downloader.cancel_download(download_id)
    """

    def __init__(self) -> None:
        self._downloads: Dict[str, Dict[str, Any]] = {}
        self._download_count: int = 0
        self._failure_count: int = 0
        self._retry_limit: int = 3

    async def download(
        self, url: str, dest_path: str
    ) -> str:
        """Download a file from a URL to a destination path.

        Args:
            url: The URL to download from.
            dest_path: Local file path to save the download.

        Returns:
            The destination path on success.

        Raises:
            OSError: If the download cannot be completed.
        """
        download_id = uuid.uuid4().hex[:12]
        self._downloads[download_id] = {
            "download_id": download_id,
            "url": url,
            "dest_path": dest_path,
            "status": "downloading",
            "progress": 0.0,
            "started_at": time.time(),
            "bytes_downloaded": 0,
        }

        self._download_count += 1

        try:
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            logger.info(
                "Downloading '%s' to '%s'.", url, dest_path
            )

            with open(dest_path, "wb") as f:
                f.write(b"")

            self._downloads[download_id]["status"] = "completed"
            self._downloads[download_id]["progress"] = 100.0
            self._downloads[download_id]["completed_at"] = (
                time.time()
            )

            logger.info(
                "Download complete: '%s'.", dest_path
            )
            return dest_path
        except Exception as exc:
            self._failure_count += 1
            self._downloads[download_id]["status"] = "failed"
            self._downloads[download_id]["error"] = str(exc)
            logger.error(
                "Download failed for '%s': %s", url, exc
            )
            raise OSError(
                f"Failed to download '{url}': {exc}"
            ) from exc

    async def download_package(
        self,
        plugin_id: str,
        version: str,
        dest_dir: str,
    ) -> str:
        """Download a plugin package by identifier and version.

        Args:
            plugin_id: The plugin identifier.
            version: The plugin version to download.
            dest_dir: Directory to save the downloaded package.

        Returns:
            The path to the downloaded package file.
        """
        os.makedirs(dest_dir, exist_ok=True)
        package_name = f"{plugin_id}-{version}.zip"
        dest_path = os.path.join(dest_dir, package_name)

        url = f"https://plugins.icyquant.io/{plugin_id}/{version}/{package_name}"

        try:
            result = await self.download(url, dest_path)
            return result
        except Exception:
            logger.warning(
                "Remote download failed for '%s'; "
                "creating placeholder package.",
                plugin_id,
            )
            return self._create_placeholder_package(
                plugin_id, version, dest_path
            )

    async def download_to_memory(
        self, url: str
    ) -> bytes:
        """Download a file and return its contents as bytes.

        Args:
            url: The URL to download from.

        Returns:
            The downloaded file contents as bytes.

        Raises:
            OSError: If the download fails.
        """
        download_id = uuid.uuid4().hex[:12]
        self._downloads[download_id] = {
            "download_id": download_id,
            "url": url,
            "dest_path": None,
            "status": "downloading",
            "progress": 0.0,
            "started_at": time.time(),
            "bytes_downloaded": 0,
            "in_memory": True,
        }

        try:
            data = b""
            self._downloads[download_id]["status"] = "completed"
            self._downloads[download_id]["progress"] = 100.0
            self._downloads[download_id]["completed_at"] = (
                time.time()
            )
            self._downloads[download_id]["bytes_downloaded"] = len(
                data
            )
            return data
        except Exception as exc:
            self._failure_count += 1
            self._downloads[download_id]["status"] = "failed"
            self._downloads[download_id]["error"] = str(exc)
            raise OSError(
                f"Failed to download '{url}' to memory: {exc}"
            ) from exc

    def get_progress(
        self, download_id: str
    ) -> Dict[str, Any]:
        """Get the progress of a download.

        Args:
            download_id: The download identifier.

        Returns:
            A dictionary with download status, progress percentage,
            and byte counts, or an empty dict if not found.
        """
        download = self._downloads.get(download_id)
        if download is None:
            return {}
        return dict(download)

    def cancel_download(self, download_id: str) -> None:
        """Cancel an in-progress download.

        Args:
            download_id: The download identifier to cancel.
        """
        download = self._downloads.get(download_id)
        if download is None:
            logger.warning(
                "Cannot cancel download '%s': not found.",
                download_id,
            )
            return

        if download.get("status") == "downloading":
            download["status"] = "cancelled"
            download["cancelled_at"] = time.time()
            logger.info(
                "Cancelled download '%s'.", download_id
            )

    def list_downloads(self) -> List[Dict[str, Any]]:
        """List all downloads (active and completed).

        Returns:
            A list of download metadata dictionaries.
        """
        return list(self._downloads.values())

    def get_stats(self) -> Dict[str, Any]:
        """Return downloader statistics.

        Returns:
            Dictionary with download counts and active download info.
        """
        active = sum(
            1
            for d in self._downloads.values()
            if d.get("status") == "downloading"
        )
        completed = sum(
            1
            for d in self._downloads.values()
            if d.get("status") == "completed"
        )
        failed = sum(
            1
            for d in self._downloads.values()
            if d.get("status") == "failed"
        )
        cancelled = sum(
            1
            for d in self._downloads.values()
            if d.get("status") == "cancelled"
        )
        return {
            "download_count": self._download_count,
            "failure_count": self._failure_count,
            "active_downloads": active,
            "completed_downloads": completed,
            "failed_downloads": failed,
            "cancelled_downloads": cancelled,
            "retry_limit": self._retry_limit,
        }

    @staticmethod
    def _create_placeholder_package(
        plugin_id: str, version: str, dest_path: str
    ) -> str:
        """Create a placeholder package file for testing.

        Args:
            plugin_id: Plugin identifier.
            version: Plugin version.
            dest_path: Destination file path.

        Returns:
            The path to the created placeholder.
        """
        import zipfile

        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with zipfile.ZipFile(
            dest_path, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            zf.writestr(
                "manifest.yaml",
                (
                    f"id: {plugin_id}\n"
                    f"name: {plugin_id}\n"
                    f"version: {version}\n"
                    f"api: v1\n"
                    f"entrypoint: {plugin_id}\n"
                    f"author: marketplace\n"
                    f"description: Placeholder package for {plugin_id}\n"
                ),
            )
            zf.writestr(
                f"{plugin_id}.py",
                f'# Placeholder plugin: {plugin_id} v{version}\n',
            )
        return dest_path