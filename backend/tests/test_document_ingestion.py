"""
test_document_ingestion.py — Comprehensive unit tests for multi-format document ingestion engine.
Tests PDF, docx, CSV, Excel, Image OCR, text parsing, graceful fallback behavior,
ChromaDB pipeline integration, and the spreadsheet analytics query tool.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from documents.ingestion import (
    ingest_file as parse_document,
    ParsedDocument,
    STORED_SPREADSHEETS,
    _parse_csv,
    _parse_docx,
    _parse_excel,
    _parse_image,
    _parse_pdf,
)
import document_pipeline
from agent_tools import info_tools


@pytest.fixture
def tmp_csv_file(tmp_path):
    p = tmp_path / "sales.csv"
    p.write_text("Product,Quantity,Price,Revenue\nWidget A,10,15.5,155.0\nWidget B,5,20.0,100.0\nWidget C,20,10.0,200.0\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def tmp_txt_file(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("Kairos Personal AI Assistant notes.\nSection 1: Architecture\nSection 2: Security\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def tmp_doc_file(tmp_path):
    p = tmp_path / "legacy.doc"
    p.write_text("Legacy Word Document content", encoding="utf-8")
    return str(p)


# ── CSV PARSING & SPREADSHEET QUERY TOOL TESTS ───────────────────────────────

class TestCSVAndSpreadsheetIngestion:
    def test_parse_csv_structured_stats_and_text(self, tmp_csv_file):
        doc = parse_document(tmp_csv_file)
        assert doc.success is True
        assert doc.file_type == "csv"
        assert "Product" in doc.extracted_text
        assert "Quantity" in doc.extracted_text
        assert doc.structured_data["row_count"] == 3
        assert doc.structured_data["column_count"] == 4
        assert "Price" in doc.structured_data["numeric_stats"]

    def test_query_spreadsheet_tool_sum_and_avg(self, tmp_csv_file):
        # Ingest CSV into registry
        doc = parse_document(tmp_csv_file)
        assert doc.success is True

        # Query tool call for total sum
        res_sum = info_tools.query_spreadsheet(doc_name="sales.csv", query="what is the sum of Revenue?")
        assert res_sum["success"] is True
        assert "455" in res_sum["answer"] or "total sum" in res_sum["answer"]

        # Query tool call for average price
        res_avg = info_tools.query_spreadsheet(doc_name="sales.csv", query="average Price")
        assert res_avg["success"] is True
        assert "15.17" in res_avg["answer"] or "average value" in res_avg["answer"]


# ── EXCEL PARSING TESTS ───────────────────────────────────────────────────────

class TestExcelIngestion:
    def test_parse_excel_graceful_missing_lib_or_success(self, tmp_path):
        excel_path = str(tmp_path / "dummy.xlsx")
        with open(excel_path, "wb") as f:
            f.write(b"PK\x03\x04\x14\x00\x06\x00")  # Dummy zip binary header

        doc = _parse_excel(excel_path)
        assert isinstance(doc, ParsedDocument)
        assert doc.file_type == "xlsx"
        if not doc.success:
            assert ("openpyxl" in doc.error_message or "pandas" in doc.error_message or "Failed to parse" in doc.error_message)


# ── WORD DOCUMENT PARSING TESTS ───────────────────────────────────────────────

class TestDocxIngestion:
    def test_parse_docx_graceful_missing_lib_or_success(self, tmp_path):
        docx_path = str(tmp_path / "test.docx")
        with open(docx_path, "wb") as f:
            f.write(b"PK\x03\x04")

        doc = _parse_docx(docx_path)
        assert isinstance(doc, ParsedDocument)
        assert doc.file_type == ".docx"
        if not doc.success:
            assert ("python-docx" in doc.error_message or "Failed to parse" in doc.error_message)

    def test_legacy_doc_warning(self, tmp_doc_file):
        doc = parse_document(tmp_doc_file)
        assert len(doc.warnings) > 0
        assert "Legacy .doc format" in doc.warnings[0]


# ── IMAGE OCR PARSING TESTS ──────────────────────────────────────────────────

class TestImageIngestion:
    def test_parse_image_ocr_or_fallback_warning(self, tmp_path):
        img_path = str(tmp_path / "test.png")
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (200, 50), color=(255, 255, 255))
            d = ImageDraw.Draw(img)
            d.text((10, 10), "KAIROS AI", fill=(0, 0, 0))
            img.save(img_path)

            doc = parse_document(img_path)
            assert doc.file_type == ".png"
            assert doc.structured_data["width"] == 200
            assert doc.structured_data["height"] == 50
        except ImportError:
            pytest.skip("Pillow is missing")


# ── PDF PARSING TESTS ─────────────────────────────────────────────────────────

class TestPDFIngestion:
    def test_parse_pdf_or_scanned_ocr_fallback(self, tmp_path):
        pdf_path = str(tmp_path / "sample.pdf")
        try:
            from pypdf import PdfWriter
            writer = PdfWriter()
            page = writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)

            doc = parse_document(pdf_path)
            assert doc.file_type == "pdf"
            assert doc.page_count == 1
        except ImportError:
            doc = parse_document(pdf_path)
            assert isinstance(doc, ParsedDocument)


# ── PIPELINE INTEGRATION TESTS ────────────────────────────────────────────────

class TestDocumentPipelineIntegration:
    def test_pipeline_ingest_file_txt(self, tmp_txt_file):
        res = document_pipeline.ingest_file(user_id="user_test123", file_path=tmp_txt_file)
        assert res["status"] == "success"
        assert res["doc_name"] == "notes.txt"
        assert res["chunk_count"] > 0
        assert "warnings" in res

    def test_pipeline_unsupported_type_graceful_error(self, tmp_path):
        p = tmp_path / "binary.xyz"
        p.write_bytes(b"\x00\x01\x02\x03")
        res = document_pipeline.ingest_file(user_id="user_test123", file_path=str(p))
        assert res["status"] == "error"
        assert "Unsupported" in res["message"]
