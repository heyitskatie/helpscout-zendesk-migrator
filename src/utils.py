"""Shared helper functions: HTML conversion, image handling, file cleanup.

Note on security: the original internal script downloaded attachments with
SSL certificate verification disabled (cert_reqs="CERT_NONE"). That is
removed here. All HTTP requests use standard certificate verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def html_to_plain_text(html: str) -> str:
    """Convert an HTML thread body to readable plain text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    return text.strip()


def extract_png_image_urls(html: str, max_images: int = 1) -> list[str]:
    """Pull out non-logo PNG image URLs embedded in an HTML thread body."""
    soup = BeautifulSoup(html, "html.parser")
    image_tags = soup.find_all("img")[:max_images]
    urls: list[str] = []
    for tag in image_tags:
        src = str(tag.get("src", ""))
        if src.lower().endswith(".png") and "logo" not in src.lower():
            urls.append(src)
    return urls


def download_image(image_url: str, destination_dir: Path) -> Path | None:
    """Download an image referenced in a thread body to a local directory."""
    if image_url.lower().startswith("cid:"):
        logger.warning("Skipping inline 'cid:' image reference: %s", image_url)
        return None

    decoded_url = unquote(image_url)
    try:
        response = requests.get(decoded_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download image %s: %s", decoded_url, exc)
        return None

    destination_dir.mkdir(parents=True, exist_ok=True)
    local_path = destination_dir / Path(urlparse(decoded_url).path).name
    local_path.write_bytes(response.content)
    return local_path


def download_attachment(attachment_url: str, destination: Path) -> bool:
    """Download an attachment with standard TLS certificate verification."""
    try:
        response = requests.get(
            attachment_url,
            headers={"User-Agent": "helpscout-zendesk-migrator/1.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download attachment %s: %s", attachment_url, exc)
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    logger.info("Attachment saved to %s", destination)
    return True


def delete_local_files(paths: list[Path]) -> None:
    """Remove locally downloaded attachments/images once they're processed."""
    for path in paths:
        try:
            if path.exists():
                path.unlink()
                logger.debug("Deleted local file: %s", path)
        except OSError as exc:
            logger.error("Could not delete %s: %s", path, exc)
