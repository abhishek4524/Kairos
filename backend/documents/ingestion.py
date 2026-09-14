"""
ingestion.py — Unified Multi-Format Document Ingestion Module for Kairos.

Supports:
1. PDF (.pdf) — pypdf / pdfplumber with OCR fallback via pytesseract + pdf2image
2. Word (.docx) — python-docx paragraph/table extraction with legacy .doc warning
3. CSV (.csv) — pandas / csv.Sniffer with structured stats + NL summary + RAG chunking
4. Excel (.xlsx) — openpyxl / pandas multi-sheet structured + NL summary
5. Images (.jpg, .jpeg, .png) — PIL + pytesseract OCR
6. Text/Markdown (.txt, .md) — Plain UTF-8 text

Designed with a graceful fallback chain: missing libraries or system binaries return
structured warnings without crashing.
"""

import os
import re
import csv
import sys
import io
import json
import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

# In-memory registry for parsed DataFrames (used by query_spreadsheet tool)
STORED_SPREADSHEETS: Dict[str, Dict[str, Any]] = {}


@dataclass
class ParsedDocument:
    extracted_text: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)
    file_type: str = ""
    page_count: int = 0
    sheet_count: int = 0
    warnings: List[str] = field(default_factory=list)
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ── 1. PDF Parser ─────────────────────────────────────────────────────────────

def _parse_pdf(file_path: str) -> ParsedDocument:
    doc = ParsedDocument(file_type="pdf")
    pages_text = []
    page_count = 0

    # Primary: try pypdf or pdfplumber
    pdf_lib_available = False
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        for p in reader.pages:
            t = p.extract_text() or ""
            if t.strip():
                pages_text.append(t.strip())
        pdf_lib_available = True
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for p in pdf.pages:
                    t = p.extract_text() or ""
                    if t.strip():
                        pages_text.append(t.strip())
            pdf_lib_available = True
        except ImportError:
            doc.warnings.append("Neither 'pypdf' nor 'pdfplumber' is installed. PDF text extraction disabled.")

    full_text = "\n\n".join(pages_text).strip()
    doc.page_count = page_count

    # OCR Fallback for scanned / image-only PDFs if text length < 50
    if len(full_text) < 50:
        ocr_text, ocr_warn = _try_pdf_ocr(file_path)
        if ocr_text.strip():
            full_text = ocr_text
            doc.warnings.append("Scanned/Image PDF detected. Extracted text using OCR.")
        if ocr_warn:
            doc.warnings.append(ocr_warn)

    if not full_text:
        doc.success = False
        doc.error_message = "No readable text could be extracted from PDF."
        return doc

    doc.extracted_text = full_text
    return doc


def _try_pdf_ocr(file_path: str) -> Tuple[str, str]:
    """Attempts OCR on PDF via pdf2image + pytesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as e:
        return "", f"Scanned PDF detected, but OCR unavailable: required library '{e.name}' is missing."

    try:
        images = convert_from_path(file_path, first_page=1, last_page=5)
        ocr_pages = []
        for img in images:
            txt = pytesseract.image_to_string(img)
            if txt.strip():
                ocr_pages.append(txt.strip())
        return "\n\n".join(ocr_pages), ""
    except Exception as exc:
        return "", f"Scanned PDF detected, but OCR failed: {exc}. (Ensure Tesseract OCR & Poppler binaries are installed)."


# ── 2. Word (.docx / .doc) Parser ─────────────────────────────────────────────

def _parse_docx(file_path: str) -> ParsedDocument:
    ext = os.path.splitext(file_path)[1].lower()
    doc = ParsedDocument(file_type=ext)

    if ext == ".doc":
        doc.warnings.append("Legacy .doc format detected. Please convert to .docx for full structural extraction.")
        # Try raw string extraction fallback
        try:
            with open(file_path, "rb") as f:
                content = f.read().decode("utf-8", errors="ignore")
                printable = "".join([c for c in content if c.isprintable() or c in "\n\t"])
                clean = re.sub(r"\s+", " ", printable).strip()
                if len(clean) > 100:
                    doc.extracted_text = clean[:5000]
                    return doc
        except Exception:
            pass
        doc.success = False
        doc.error_message = "Legacy .doc format not directly supported. Please convert file to .docx."
        return doc

    try:
        import docx
    except ImportError:
        doc.success = False
        doc.error_message = "python-docx library is missing. Install via 'pip install python-docx'."
        return doc

    try:
        d = docx.Document(file_path)
        elements = []
        
        # Paragraphs & Headings
        for p in d.paragraphs:
            if p.text.strip():
                elements.append(p.text.strip())

        # Tables
        table_count = len(d.tables)
        for t in d.tables:
            table_rows = []
            for row in t.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(" | ".join(row_cells))
            if table_rows:
                elements.append("\n[Table]\n" + "\n".join(table_rows) + "\n")

        doc.extracted_text = "\n\n".join(elements)
        doc.structured_data = {"paragraph_count": len(d.paragraphs), "table_count": table_count}
        if not doc.extracted_text:
            doc.warnings.append("Word document appears to be empty.")
        return doc

    except Exception as exc:
        doc.success = False
        doc.error_message = f"Failed to parse Word document: {exc}"
        return doc


# ── 3. CSV Parser ─────────────────────────────────────────────────────────────

def _parse_csv(file_path: str) -> ParsedDocument:
    doc = ParsedDocument(file_type="csv")
    doc_name = os.path.basename(file_path)

    try:
        import pandas as pd
    except ImportError:
        # Fallback to built-in csv module
        return _parse_csv_builtin(file_path)

    try:
        # Try pandas with auto delimiter detection
        try:
            df = pd.read_csv(file_path)
        except Exception:
            # Fallback delimiter detection via csv.Sniffer
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                sample = f.read(4096)
                dialect = csv.Sniffer().sniff(sample)
                delim = dialect.delimiter
            df = pd.read_csv(file_path, sep=delim)

        cols = list(df.columns)
        num_rows, num_cols = df.shape
        doc.page_count = 1

        # Summary statistics for numeric columns
        stats = {}
        for c in df.select_dtypes(include=["number"]).columns:
            stats[str(c)] = {
                "min": float(df[c].min()) if not df[c].empty else 0,
                "max": float(df[c].max()) if not df[c].empty else 0,
                "mean": round(float(df[c].mean()), 2) if not df[c].empty else 0,
                "sum": round(float(df[c].sum()), 2) if not df[c].empty else 0,
            }

        # First 5 sample rows as dictionary
        sample_dict = df.head(5).to_dict(orient="records")

        doc.structured_data = {
            "columns": cols,
            "row_count": num_rows,
            "column_count": num_cols,
            "numeric_stats": stats,
            "sample_rows": sample_dict,
        }

        # Store DataFrame in global registry for query_spreadsheet tool
        STORED_SPREADSHEETS[doc_name] = {"default": df}

        # Construct natural language summary text for RAG chunking
        nl_lines = [
            f"### 📊 CSV Document Summary: {doc_name}",
            f"- **Total Rows**: {num_rows}",
            f"- **Total Columns**: {num_cols}",
            f"- **Column Names**: {', '.join([str(c) for c in cols])}",
        ]
        if stats:
            nl_lines.append("- **Numeric Column Statistics**:")
            for col_name, st in stats.items():
                nl_lines.append(f"  - `{col_name}`: Sum={st['sum']}, Mean={st['mean']}, Min={st['min']}, Max={st['max']}")

        nl_lines.append("\n**Data Sample (First 5 Rows)**:")
        nl_lines.append(df.head(5).to_markdown(index=False))

        # Append markdown table of entire small CSV or chunks
        if num_rows <= 100:
            nl_lines.append("\n**Full Table Data**:")
            nl_lines.append(df.to_markdown(index=False))
        else:
            nl_lines.append(f"\n*(Truncated: showing 5 of {num_rows} total rows. Use spreadsheet query tool for full analytics)*")

        doc.extracted_text = "\n".join(nl_lines)
        return doc

    except Exception as exc:
        doc.warnings.append(f"Pandas CSV parsing failed: {exc}. Falling back to standard CSV reader.")
        return _parse_csv_builtin(file_path)


def _parse_csv_builtin(file_path: str) -> ParsedDocument:
    doc = ParsedDocument(file_type="csv")
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            doc.success = False
            doc.error_message = "CSV file is empty."
            return doc
        headers = rows[0]
        data_rows = rows[1:]
        doc.structured_data = {"columns": headers, "row_count": len(data_rows)}
        text_lines = [f"CSV Headers: {', '.join(headers)}", f"Total Rows: {len(data_rows)}"]
        for r in data_rows[:20]:
            text_lines.append(" | ".join(r))
        doc.extracted_text = "\n".join(text_lines)
        return doc
    except Exception as e:
        doc.success = False
        doc.error_message = f"CSV parsing failed: {e}"
        return doc


# ── 4. Excel (.xlsx) Parser ───────────────────────────────────────────────────

def _parse_excel(file_path: str) -> ParsedDocument:
    doc = ParsedDocument(file_type="xlsx")
    doc_name = os.path.basename(file_path)

    try:
        import pandas as pd
    except ImportError:
        doc.success = False
        doc.error_message = "pandas and openpyxl are required for Excel parsing. Run 'pip install pandas openpyxl'."
        return doc

    try:
        # Read all sheets into dict of DataFrames
        excel_file = pd.read_excel(file_path, sheet_name=None)
        doc.sheet_count = len(excel_file)
        
        sheet_summaries = []
        sheets_data = {}
        sheets_registry = {}

        for sheet_name, df in excel_file.items():
            sheets_registry[sheet_name] = df
            cols = list(df.columns)
            num_rows, num_cols = df.shape
            
            stats = {}
            for c in df.select_dtypes(include=["number"]).columns:
                stats[str(c)] = {
                    "min": float(df[c].min()) if not df[c].empty else 0,
                    "max": float(df[c].max()) if not df[c].empty else 0,
                    "mean": round(float(df[c].mean()), 2) if not df[c].empty else 0,
                    "sum": round(float(df[c].sum()), 2) if not df[c].empty else 0,
                }

            sheets_data[sheet_name] = {
                "columns": [str(c) for c in cols],
                "row_count": num_rows,
                "numeric_stats": stats,
                "sample_rows": df.head(5).to_dict(orient="records"),
            }

            s_lines = [
                f"#### Sheet: {sheet_name}",
                f"- **Rows**: {num_rows}, **Columns**: {num_cols}",
                f"- **Columns**: {', '.join([str(c) for c in cols])}",
            ]
            if stats:
                s_lines.append("- **Numeric Column Statistics**:")
                for col_name, st in stats.items():
                    s_lines.append(f"  - `{col_name}`: Sum={st['sum']}, Mean={st['mean']}, Min={st['min']}, Max={st['max']}")

            s_lines.append("\n**Sample Data**:")
            s_lines.append(df.head(5).to_markdown(index=False))
            sheet_summaries.append("\n".join(s_lines))

        STORED_SPREADSHEETS[doc_name] = sheets_registry

        doc.structured_data = {
            "sheet_count": doc.sheet_count,
            "sheets": sheets_data,
        }

        full_nl = [
            f"### 📈 Excel Workbook Summary: {doc_name}",
            f"- **Total Sheets**: {doc.sheet_count} ({', '.join(excel_file.keys())})\n",
            "\n\n".join(sheet_summaries)
        ]
        doc.extracted_text = "\n".join(full_nl)
        return doc

    except Exception as exc:
        doc.success = False
        doc.error_message = f"Failed to parse Excel workbook: {exc} (Ensure openpyxl is installed)."
        return doc


# ── 5. Image Parser (OCR) ──────────────────────────────────────────────────────

def _parse_image(file_path: str) -> ParsedDocument:
    ext = os.path.splitext(file_path)[1].lower()
    doc = ParsedDocument(file_type=ext)

    try:
        from PIL import Image
    except ImportError:
        doc.success = False
        doc.error_message = "Pillow library is missing. Run 'pip install Pillow'."
        return doc

    try:
        img = Image.open(file_path)
        doc.structured_data = {"width": img.width, "height": img.height, "format": img.format}
    except Exception as exc:
        doc.success = False
        doc.error_message = f"Failed to open image file: {exc}"
        return doc

    # OCR extraction via pytesseract
    try:
        import pytesseract
        ocr_text = pytesseract.image_to_string(img)
        if ocr_text.strip():
            doc.extracted_text = f"Image Document Text (OCR):\n{ocr_text.strip()}"
        else:
            doc.extracted_text = f"Image file '{os.path.basename(file_path)}' ({img.width}x{img.height}). No embedded text detected via OCR."
            doc.warnings.append("OCR completed but no readable text was detected in the image.")
    except Exception as exc:
        doc.extracted_text = f"Image file '{os.path.basename(file_path)}' ({img.width}x{img.height})."
        doc.warnings.append(f"Image uploaded, but OCR unavailable: {exc}. Install Tesseract OCR to enable text extraction from images.")

    return doc


# ── 6. Text / Markdown Parser ─────────────────────────────────────────────────

def _parse_text(file_path: str) -> ParsedDocument:
    ext = os.path.splitext(file_path)[1].lower()
    doc = ParsedDocument(file_type=ext)
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            doc.extracted_text = f.read().strip()
        if not doc.extracted_text:
            doc.warnings.append("Text file is empty.")
        return doc
    except Exception as exc:
        doc.success = False
        doc.error_message = f"Failed to read text file: {exc}"
        return doc


# ── Main Unified Ingestion Entry Point ────────────────────────────────────────

def ingest_file(file_path: str) -> ParsedDocument:
    """
    Main entry point: dispatches by file extension to format-specific parsers.
    Returns ParsedDocument object containing extracted text, structured data,
    counts, and warnings.
    """
    if not os.path.exists(file_path):
        return ParsedDocument(
            success=False,
            error_message=f"File not found: {file_path}"
        )

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_path)
    elif ext == ".csv":
        return _parse_csv(file_path)
    elif ext in (".xlsx", ".xls"):
        return _parse_excel(file_path)
    elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        return _parse_image(file_path)
    elif ext in (".txt", ".md", ".json", ".log"):
        return _parse_text(file_path)
    else:
        return ParsedDocument(
            file_type=ext,
            success=False,
            error_message=f"Unsupported file type '{ext}'. Supported: .pdf, .docx, .csv, .xlsx, .jpg, .png, .txt, .md"
        )
