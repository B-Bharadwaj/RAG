"""
pipeline/loader.py

Extended from v1 to support Excel and CSV in addition to PDF.

v1: load_pdf(), extract_images()
v2 additions:
    - load_excel()  — handles single and multi-sheet workbooks
    - load_csv()    — loads CSV into a DataFrame
    - load_file()   — master router, detects file type automatically
    - FileData      — unified container for any file type
"""

import os
import io
import pandas as pd
from pypdf import PdfReader
import fitz
from PIL import Image
from dataclasses import dataclass, field


# ── Unified data container ─────────────────────────────────────────────────

@dataclass
class FileData:
    """
    Unified container for any uploaded file.
    Regardless of file type, everything ends up here.
    """
    file_name:   str
    file_type:   str                         # "pdf", "excel", "csv"

    # PDF specific
    pages:       list[tuple[int, str]] = field(default_factory=list)

    # Excel / CSV specific
    dataframes:  dict[str, pd.DataFrame] = field(default_factory=dict)
    # key   = sheet name (CSV uses filename as sheet name)
    # value = DataFrame for that sheet

    # Shared metadata
    row_count:   int = 0
    col_count:   int = 0
    sheet_names: list[str] = field(default_factory=list)


# ── Master router ──────────────────────────────────────────────────────────

def load_file(file_path: str, file_name: str) -> FileData:
    """
    Detect file type and route to the correct loader.

    Parameters
    ----------
    file_path : path to saved file on disk
    file_name : original uploaded filename (used for type detection)

    Returns
    -------
    FileData object with all content loaded
    """
    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".pdf":
        return _load_pdf(file_path, file_name)
    elif ext in (".xlsx", ".xls"):
        return _load_excel(file_path, file_name)
    elif ext == ".csv":
        return _load_csv(file_path, file_name)
    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported: .pdf, .xlsx, .xls, .csv"
        )


# ── PDF Loader (from v1 — unchanged) ──────────────────────────────────────

def load_pdf(file_path: str) -> list[tuple[int, str]]:
    """
    Extract text from each page of a PDF.
    Kept for backward compatibility with v1 pipeline.

    Returns
    -------
    list of (page_num: int, page_text: str) — 1-indexed
    """
    reader = PdfReader(file_path)
    pages_text = []
    for page_num, page in enumerate(reader.pages):
        extracted = page.extract_text()
        if extracted:
            pages_text.append((page_num + 1, extracted))
    return pages_text


def extract_images(pdf_path: str) -> list[tuple[int, Image.Image]]:
    """
    Rasterise each PDF page to a PIL Image at 200 dpi.
    Kept for backward compatibility with v1 pipeline.

    Returns
    -------
    list of (page_num: int, PIL.Image) — 1-indexed
    """
    pdf = fitz.open(pdf_path)
    images = []
    for page_num, page in enumerate(pdf):
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        images.append((page_num + 1, img))
    pdf.close()
    return images


def _load_pdf(file_path: str, file_name: str) -> FileData:
    """Internal PDF loader that returns a FileData object."""
    pages_text = load_pdf(file_path)
    return FileData(
        file_name = file_name,
        file_type = "pdf",
        pages     = pages_text,
        row_count = len(pages_text),
    )


# ── Excel Loader (NEW) ─────────────────────────────────────────────────────

def _load_excel(file_path: str, file_name: str) -> FileData:
    """
    Load an Excel file — handles single and multi-sheet workbooks.
    Each sheet becomes a separate DataFrame in FileData.dataframes.
    """
    excel_file  = pd.ExcelFile(file_path)
    sheet_names = excel_file.sheet_names
    dataframes  = {}

    for sheet in sheet_names:
        df = pd.read_excel(
            file_path,
            sheet_name = sheet,
            engine     = "openpyxl"
        )
        # Drop completely empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df = df.reset_index(drop=True)

        # Convert date columns to strings to avoid JSON issues later
        for col in df.select_dtypes(include=["datetime64"]).columns:
            df[col] = df[col].astype(str)

        dataframes[sheet] = df

    first_df = dataframes[sheet_names[0]]

    return FileData(
        file_name   = file_name,
        file_type   = "excel",
        dataframes  = dataframes,
        sheet_names = sheet_names,
        row_count   = len(first_df),
        col_count   = len(first_df.columns),
    )


# ── CSV Loader (NEW) ───────────────────────────────────────────────────────

def _load_csv(file_path: str, file_name: str) -> FileData:
    """
    Load a CSV file into a DataFrame.
    Uses filename as sheet name for consistency with Excel loader.
    """
    # Try UTF-8 first, fall back to Windows encoding
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin-1")

    # Drop completely empty rows and columns
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = df.reset_index(drop=True)

    # Convert date columns to strings
    for col in df.select_dtypes(include=["datetime64"]).columns:
        df[col] = df[col].astype(str)

    sheet_name = os.path.splitext(file_name)[0]

    return FileData(
        file_name   = file_name,
        file_type   = "csv",
        dataframes  = {sheet_name: df},
        sheet_names = [sheet_name],
        row_count   = len(df),
        col_count   = len(df.columns),
    )


# ── Quick test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python loader.py <file_path>")
        sys.exit(1)

    path = sys.argv[1]
    name = os.path.basename(path)
    data = load_file(path, name)

    print(f"\nFile     : {data.file_name}")
    print(f"Type     : {data.file_type}")
    print(f"Rows     : {data.row_count}")
    print(f"Columns  : {data.col_count}")

    if data.file_type in ("excel", "csv"):
        for sheet, df in data.dataframes.items():
            print(f"\nSheet    : {sheet}")
            print(df.head(3))
    elif data.file_type == "pdf":
        for page_num, text in data.pages[:2]:
            print(f"\nPage {page_num}:")
            print(text[:300])
