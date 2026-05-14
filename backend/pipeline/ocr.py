"""
pipeline/ocr.py
Groq Vision captioning for PDF page images.

Each page is processed by PyMuPDF which detects figure bounding boxes.
Each detected figure is cropped, saved as a PNG, and sent to Groq Vision
individually. This means the UI shows just the figure, not the whole page.

storage/images/<doc_id>_p<page>_fig<n>.png  — one file per detected figure
"""

import base64
import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from groq import Groq
from config import GROQ_API_KEY, GROQ_VISION_MODEL, OCR_MAX_WORKERS

client = Groq(api_key=GROQ_API_KEY)

IMAGES_DIR = os.path.join("storage", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

_VISION_PROMPT = """You are analyzing a figure, diagram, or chart from an academic research paper.
Describe everything visible including:
- All components, labels, arrows, and connections
- Axis labels, legend entries, and key values if it is a graph or plot
- Layer names, data flow directions, and annotations if it is an architecture diagram
- All rows, columns, and cell values if it is a table

Be specific. Include all numbers and labels you can see.
If this image contains only plain text with no figures or diagrams, reply exactly: TEXT PAGE - no figures"""


def image_to_base64(img) -> str:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _extract_figure_crops(pdf_path: str, page_num: int, dpi: int = 200):
    """
    Detect and crop figures from a single PDF page using PyMuPDF.
    Returns list of (fig_index, PIL.Image) tuples.
    Falls back to full-page render if no figures detected.
    """
    import fitz
    from PIL import Image

    crops = []

    try:
        pdf  = fitz.open(pdf_path)
        page = pdf[page_num - 1]          # page_num is 1-indexed
        mat  = fitz.Matrix(dpi / 72, dpi / 72)

        # Method 1: embedded raster images (photos, exported diagrams)
        for img_info in page.get_images(full=True):
            xref  = img_info[0]
            rects = page.get_image_rects(xref)
            for rect in rects:
                if rect.width < 40 or rect.height < 40:
                    continue                      # skip tiny icons/bullets
                pix     = page.get_pixmap(matrix=mat, clip=fitz.Rect(rect))
                pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                crops.append(pil_img)

        # Method 2: vector drawings (drawn-in diagrams like Fig 3 CNN)
        if not crops:
            drawings = page.get_drawings()
            if drawings:
                all_rects = [fitz.Rect(d["rect"]) for d in drawings if d.get("rect")]
                if all_rects:
                    merged = all_rects[0]
                    for r in all_rects[1:]:
                        merged = merged | r           # union all drawing rects
                    pad    = 10 * (72 / dpi)
                    merged = (merged + fitz.Rect(-pad, -pad, pad, pad)) & page.rect
                    if merged.width > 50 and merged.height > 50:
                        pix     = page.get_pixmap(matrix=mat, clip=merged)
                        pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                        crops.append(pil_img)

        pdf.close()

    except Exception as e:
        print(f"Figure detection failed page {page_num}: {e}")

    # Fallback: full page render
    if not crops:
        try:
            import fitz as _fitz
            from PIL import Image as _Image
            pdf2    = _fitz.open(pdf_path)
            page2   = pdf2[page_num - 1]
            pix     = page2.get_pixmap(matrix=_fitz.Matrix(dpi / 72, dpi / 72))
            pil_img = _Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            crops.append(pil_img)
            pdf2.close()
        except Exception as e:
            print(f"Full-page fallback failed page {page_num}: {e}")

    return [(i, img) for i, img in enumerate(crops)]


def _caption_page(
    page_num: int,
    pdf_path: str,
    pdf_name: str,
    doc_id: str,
) -> list[dict]:
    """Caption all detected figures on one page. Returns list of doc dicts."""
    results = []
    try:
        figure_crops = _extract_figure_crops(pdf_path, page_num)
        for fig_idx, pil_img in figure_crops:
            try:
                response = client.chat.completions.create(
                    model=GROQ_VISION_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/png;base64,{image_to_base64(pil_img)}"}},
                            {"type": "text", "text": _VISION_PROMPT},
                        ],
                    }],
                    max_tokens=1024,
                )
                description = response.choices[0].message.content.strip()

                if "TEXT PAGE - no figures" in description or len(description) < 30:
                    continue

                # Save the cropped figure PNG
                fname      = f"{doc_id}_p{page_num}_fig{fig_idx}.png"
                image_path = os.path.join(IMAGES_DIR, fname)
                pil_img.save(image_path, format="PNG")

                results.append({
                    "page_num": page_num,
                    "text":     description,
                    "type":     "image",
                    "metadata": {
                        "source":     "groq_vision",
                        "page":       page_num,
                        "pdf":        pdf_name,
                        "doc_id":     doc_id,
                        "image_path": image_path,
                        "fig_index":  fig_idx,
                    },
                })

            except Exception as e:
                print(f"Caption failed p{page_num} fig{fig_idx}: {e}")

    except Exception as e:
        print(f"Page {page_num} failed: {e}")

    return results


def _caption_page_fullpage(
    page_num: int, img, pdf_name: str, doc_id: str
) -> dict | None:
    """Fallback: caption and save the full page image (original behaviour)."""
    try:
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{image_to_base64(img)}"}},
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
            max_tokens=1024,
        )
        description = response.choices[0].message.content.strip()

        if "TEXT PAGE - no figures" in description or len(description) < 30:
            return None

        fname      = f"{doc_id}_p{page_num}.png"
        image_path = os.path.join(IMAGES_DIR, fname)
        img.save(image_path, format="PNG")

        return {
            "page_num": page_num,
            "text":     description,
            "type":     "image",
            "metadata": {
                "source":     "groq_vision",
                "page":       page_num,
                "pdf":        pdf_name,
                "doc_id":     doc_id,
                "image_path": image_path,
            },
        }

    except Exception as e:
        print(f"Page {page_num} failed: {e}")
        return None


def caption_images(
    images,
    pdf_name: str = "unknown",
    doc_id: str = "unknown",
    progress_callback=None,
    pdf_path: str = None,
) -> list[dict]:
    """
    Run Groq Vision over a list of (page_num, PIL.Image) tuples in parallel.

    If pdf_path is provided, uses PyMuPDF to extract cropped figures per page
    so only the figure itself is saved and shown — not the whole page.

    Parameters
    ----------
    images            : list of (page_num: int, PIL.Image)
    pdf_name          : original filename
    doc_id            : UUID for scoped deletion
    progress_callback : optional callable(completed: int, total: int)
    pdf_path          : path to the original PDF — enables figure cropping

    Returns
    -------
    list of image document dicts sorted by page then figure index
    """
    total = len(images)
    if total == 0:
        return []

    completed = 0
    all_results: list[dict] = []

    if pdf_path:
        # Figure-crop mode
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_caption_page, pn, pdf_path, pdf_name, doc_id): pn
                for pn, _ in images
            }
            for future in as_completed(futures):
                pn = futures[future]
                completed += 1
                docs = future.result()
                all_results.extend(docs)
                label = f"{len(docs)} figure(s)" if docs else "no figures"
                print(f"Page {pn}: {label} ({completed}/{total})")
                if progress_callback:
                    progress_callback(completed, total)
    else:
        # Full-page fallback
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_caption_page_fullpage, pn, img, pdf_name, doc_id): pn
                for pn, img in images
            }
            for future in as_completed(futures):
                pn = futures[future]
                completed += 1
                doc = future.result()
                if doc:
                    all_results.append(doc)
                    print(f"Page {pn}: captured ({completed}/{total})")
                else:
                    print(f"Page {pn}: skipped ({completed}/{total})")
                if progress_callback:
                    progress_callback(completed, total)

    all_results.sort(key=lambda d: (d["page_num"], d.get("metadata", {}).get("fig_index", 0)))

    for doc in all_results:
        doc.pop("page_num", None)

    return all_results
