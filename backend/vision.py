import base64
import logging

import pymupdf

import config
from db import get_db

logger = logging.getLogger(__name__)

VISION_PROMPT = (
    "You are analyzing a single rendered page from a Swedish construction tender "
    "(FFU) document. Describe the visual content that plain text extraction would "
    "miss: tables (report their structure and key rows/values), drawings, plans, "
    "diagrams, stamps, and handwritten notes. Be concise and factual. Answer in the "
    "same language as the page (usually Swedish). If the page is plain prose with no "
    "visual elements, say so briefly."
)


def _render_page_png(abs_path, page_number: int) -> bytes:
    """Render a 1-based PDF page number to PNG bytes at 150 dpi."""
    doc = pymupdf.open(str(abs_path))
    try:
        index = page_number - 1
        if index < 0 or index >= doc.page_count:
            raise ValueError(f"page {page_number} out of range (1..{doc.page_count})")
        page = doc.load_page(index)
        pix = page.get_pixmap(dpi=150)
        return pix.tobytes("png")
    finally:
        doc.close()


def view_page(document_id: int, page: int) -> str:
    """Render a PDF page to an image and have the vision model describe it.
    Returns a text description, or a human-readable error string on failure."""
    row = get_db().execute(
        "SELECT filename, rel_path FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not row:
        return "Document not found."
    if not row["rel_path"]:
        return "Document has no file on disk."
    data_root = config.DATA_DIR.resolve()
    abs_path = (config.DATA_DIR / row["rel_path"]).resolve()
    if not abs_path.is_relative_to(data_root):
        return "Invalid document path."
    if abs_path.suffix.lower() != ".pdf":
        return "Visual view is only available for PDF documents."
    try:
        png = _render_page_png(abs_path, page)
    except Exception as e:
        logger.warning(f"Render failed for doc {document_id} page {page}: {e}")
        return f"Could not render page {page}: {e}"
    b64 = base64.b64encode(png).decode()
    try:
        resp = config.client().chat.completions.create(
            model=config.VISION_MODEL,
            messages=[
                {"role": "system", "content": VISION_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Describe page {page} of {row['filename']}.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            max_tokens=700,
        )
        return resp.choices[0].message.content or "(no visual description returned)"
    except Exception as e:
        logger.warning(f"Vision call failed for doc {document_id} page {page}: {e}")
        return f"Vision analysis failed: {e}"
