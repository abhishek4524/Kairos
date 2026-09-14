# Kairos Multi-Format Document Ingestion Engine (`backend/documents/`)

This directory houses the multi-format document ingestion engine for Kairos, allowing users to ingest, parse, chunk, embed, and query a wide range of document types.

---

## 📄 Supported File Types & Parser Matrix

| Format | File Extension(s) | Primary Parser / Library | Optional System Dependency | Fallback Behavior |
|---|---|---|---|---|
| **PDF** | `.pdf` | `pypdf` / `pdfplumber` | Tesseract OCR + Poppler (for scanned PDFs) | If scanned/image-only PDF detected, attempts OCR via `pytesseract` + `pdf2image`. Returns clear warning if Tesseract is missing. |
| **Word** | `.docx` | `python-docx` | None | Extracts headings, paragraphs, and tables. Warns on legacy `.doc` files. |
| **CSV** | `.csv` | `pandas` | None | Falls back to Python's `csv.Sniffer` / `csv.reader`. Generates structured stats + natural-language summary. |
| **Excel** | `.xlsx`, `.xls` | `openpyxl` via `pandas` | None | Reads all workbook sheets, producing per-sheet structured stats and sample table summaries. |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.bmp` | `Pillow` + `pytesseract` | Tesseract OCR binary | Extracts text via OCR. If Tesseract is not installed, returns metadata with a clear warning without crashing. |
| **Text** | `.txt`, `.md`, `.json`, `.log` | Built-in UTF-8 reader | None | Direct text extraction. |

---

## 🛠️ Installation Instructions

### 1. Python Dependencies
Install required Python libraries via `pip`:

```bash
pip install pypdf pdfplumber python-docx pandas openpyxl pillow pytesseract pdf2image
```

---

### 2. System Binary Dependencies (Optional — For OCR & PDF Image Extraction)

#### A. Tesseract OCR (For scanned PDFs & Image OCR)

- **Windows**:
  - Install via Winget: `winget install UB-Mannheim.TesseractOCR`
  - Or download installer from GitHub: [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
  - Add `C:\Program Files\Tesseract-OCR` to your System `PATH`.
- **macOS**:
  ```bash
  brew install tesseract
  ```
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt-get update && sudo apt-get install -y tesseract-ocr
  ```

#### B. Poppler Utilities (For `pdf2image` scanned PDF rendering)

- **Windows**:
  - Download Poppler binary for Windows (e.g. from [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases/))
  - Extract and add `poppler-xx/Library/bin` to System `PATH`.
- **macOS**:
  ```bash
  brew install poppler
  ```
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt-get install -y poppler-utils
  ```

---

## 📊 Analytics & Spreadsheet Computation Tool (`query_spreadsheet`)

For CSV and Excel files, Kairos doesn't just chunk raw text into vector storage — it also keeps the structured DataFrame in memory.

When users ask numeric or aggregate questions ("what is the total sales in column Y?", "average price"), Kairos routes the question through the `query_spreadsheet` tool, executing actual `pandas` computations instead of guessing from embedded text chunks.
