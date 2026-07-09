import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils import extract_png_image_urls, html_to_plain_text


def test_html_to_plain_text_strips_tags():
    html = "<p>Hello world</p>"
    assert html_to_plain_text(html) == "Hello world"


def test_html_to_plain_text_separates_block_elements():
    html = "<p>Line one</p><p>Line two</p>"
    assert html_to_plain_text(html) == "Line one\nLine two"


def test_html_to_plain_text_handles_empty_string():
    assert html_to_plain_text("") == ""


def test_extract_png_image_urls_filters_logos():
    html = (
        '<img src="https://example.com/logo.png">'
        '<img src="https://example.com/screenshot.png">'
        '<img src="https://example.com/photo.jpg">'
    )
    result = extract_png_image_urls(html, max_images=5)
    assert result == ["https://example.com/screenshot.png"]


def test_extract_png_image_urls_respects_max_images():
    html = "".join(f'<img src="https://example.com/img{i}.png">' for i in range(5))
    result = extract_png_image_urls(html, max_images=2)
    assert len(result) == 2
