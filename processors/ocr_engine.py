"""
ocr_engine.py
-------------
Vision-LLM-powered bill extraction for MediAudit.

Strategy (zero OCR dependencies, no model downloads):
  Image / Camera → base64 encode → Groq Vision (llama-3.2-11b-vision-preview)
  PDF            → pypdfium2 renders each page to JPEG → same Groq Vision path

The Groq Vision model reads the bill like a human and returns structured
Markdown with every line item, date, amount, and diagnosis it can see.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Vision model — fastest Groq vision model with strong OCR capability
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


# Prompt sent with every image
VISION_PROMPT = """You are a medical bill data extractor.

Carefully read every detail visible in this medical bill / discharge summary image and extract:

1. Patient details (name, age, gender, patient ID if visible)
2. Hospital / clinic name and date(s) of service
3. Diagnosis / chief complaint
4. Every line item charge (treatment name, quantity, unit cost, total cost)
5. Subtotal, taxes, discounts, and grand total
6. Doctor name(s) and department(s)
7. Any pre-existing conditions or co-morbidities mentioned
8. Insurance / TPA details if printed on the bill

Format your response as clean, structured Markdown with clear headings and
a table for the line items. Be precise with all numbers and currency symbols.
If any field is not visible, write "Not visible" for that field.
Do not add commentary or assumptions — extract only what is printed."""


# ---------------------------------------------------------------------------
# Internal: encode image bytes to base64 data URI
# ---------------------------------------------------------------------------

def _to_base64_jpeg(image_bytes: bytes, filename: str) -> tuple[str, str]:
    """
    Return (base64_string, media_type) for an image.
    Converts non-JPEG formats to JPEG via PIL for consistent Groq input.
    """
    from PIL import Image  # type: ignore

    lower = filename.lower()

    # If already JPEG, use as-is
    if lower.endswith((".jpg", ".jpeg")):
        return base64.b64encode(image_bytes).decode(), "image/jpeg"

    # Convert PNG / TIFF / BMP / WEBP → JPEG
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


# ---------------------------------------------------------------------------
# Internal: render PDF pages to JPEG images
# ---------------------------------------------------------------------------

def _pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    """
    Render every page of a PDF to a JPEG byte string using pypdfium2.
    Returns a list of raw JPEG bytes, one per page.
    """
    import pypdfium2 as pdfium  # type: ignore

    pdf = pdfium.PdfDocument(pdf_bytes)
    jpegs: list[bytes] = []

    for page_index in range(len(pdf)):
        page = pdf[page_index]
        # Render at 150 DPI (scale=150/72 ≈ 2.08) — clear enough for LLM vision
        bitmap = page.render(scale=150 / 72, rotation=0)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="JPEG", quality=92)
        jpegs.append(buf.getvalue())
        logger.info("Rendered PDF page %d to JPEG (%d bytes)", page_index + 1, len(buf.getvalue()))

    return jpegs


# ---------------------------------------------------------------------------
# Internal: call Groq Vision on a single image
# ---------------------------------------------------------------------------

def _vision_extract(
    groq_client,  # groq.Groq instance
    image_b64: str,
    media_type: str,
    page_label: str = "Bill",
) -> str:
    """Send one image to Groq Vision and return the extracted Markdown text."""
    response = groq_client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": f"[{page_label}]\n\n{VISION_PROMPT}",
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_from_bytes(
    file_bytes: bytes,
    filename: str,
    groq_client,  # groq.Groq instance — passed in from app.py
) -> str:
    """
    Extract structured bill details from a document using Groq Vision.

    Routing:
      • PDF   → rendered page-by-page to JPEG → each page sent to Groq Vision
                 → all page extractions concatenated
      • Image → base64 encoded → sent directly to Groq Vision

    Args:
        file_bytes:  Raw binary content of the bill.
        filename:    Original filename (determines routing).
        groq_client: Initialised groq.Groq() client.

    Returns:
        Structured Markdown string of all extracted bill details.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        logger.info("PDF detected — rendering pages to JPEG for Groq Vision…")
        page_images = _pdf_to_images(file_bytes)

        if not page_images:
            return "[PDF rendering failed — no pages found]"

        page_texts: list[str] = []
        for i, jpeg_bytes in enumerate(page_images, 1):
            b64 = base64.b64encode(jpeg_bytes).decode()
            label = f"Page {i} of {len(page_images)}"
            logger.info("Sending %s to Groq Vision…", label)
            text = _vision_extract(groq_client, b64, "image/jpeg", label)
            page_texts.append(f"## {label}\n\n{text}")

        return "\n\n---\n\n".join(page_texts)

    else:
        # Image file (PNG, JPG, TIFF, camera capture)
        logger.info("Image detected — sending to Groq Vision…")
        b64, media_type = _to_base64_jpeg(file_bytes, filename)
        return _vision_extract(groq_client, b64, media_type, "Medical Bill")


def extract_text_from_path(
    file_path: str | Path,
    groq_client,
) -> str:
    """
    Convenience wrapper: read a file from disk, then call extract_text_from_bytes.

    Args:
        file_path:   Path to the document.
        groq_client: Initialised groq.Groq() client.

    Returns:
        Structured Markdown string of extracted bill details.
    """
    path = Path(file_path)
    return extract_text_from_bytes(path.read_bytes(), path.name, groq_client)