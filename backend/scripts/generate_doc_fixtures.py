"""
One-off generator for tests/fixtures/documents/*. Not run automatically —
re-run manually if the fixtures ever need regenerating:

    .venv/bin/python scripts/generate_doc_fixtures.py

Produces genuinely real files (not hand-crafted byte strings pretending to
be a PDF): a DOCX authored with python-docx, converted to a real
multi-paragraph native-text PDF via LibreOffice headless, an image-only
PDF with no text layer at all (for exercising the OCR-needed path), a
real XLSX, and a ZIP bundling two of them — matching the formats brief
§7 calls out (PDF/DOC/DOCX/XLS/XLSX/ZIP).
"""
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pdf2image import convert_from_path
from PIL import Image

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "documents"


def make_docx() -> Path:
    doc = Document()
    doc.add_heading("Sample Tender Notice", level=1)
    doc.add_paragraph(
        "This is a native-text document generated for Sprint 3 document processing tests. "
        "It contains real paragraphs so pypdf/python-docx extraction can be verified against "
        "known expected text, not a mock."
    )
    doc.add_paragraph("Minimum average annual turnover: Rs. 10,00,00,000 (Rupees Ten Crore only).")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Item"
    table.rows[0].cells[1].text = "Quantity"
    table.rows[1].cells[0].text = "Laptops"
    table.rows[1].cells[1].text = "25"

    path = FIXTURES_DIR / "sample_native.docx"
    doc.save(path)
    return path


def make_native_pdf(docx_path: Path) -> Path:
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(FIXTURES_DIR), str(docx_path)],
        check=True,
        capture_output=True,
    )
    return FIXTURES_DIR / "sample_native.pdf"


def make_scanned_pdf(native_pdf_path: Path) -> Path:
    """Rasterises the native PDF's first page into an image, then saves
    that image back out as a PDF with no text layer at all — a faithful
    stand-in for a scanned document, not a mock of one."""
    images = convert_from_path(str(native_pdf_path), dpi=150)
    first_page: Image.Image = images[0]
    path = FIXTURES_DIR / "sample_scanned.pdf"
    first_page.save(path, "PDF")
    return path


def make_xlsx() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item", "Description", "Quantity", "Unit Price"])
    ws.append(["1", "Laptop - 16GB RAM", 25, 55000])
    ws.append(["2", "Networking Switch 24-port", 5, 18000])
    path = FIXTURES_DIR / "sample.xlsx"
    wb.save(path)
    return path


def make_zip(pdf_path: Path, xlsx_path: Path) -> Path:
    path = FIXTURES_DIR / "sample_bundle.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(pdf_path, arcname="NIT.pdf")
        zf.write(xlsx_path, arcname="BOQ.xlsx")
    return path


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = make_docx()
    pdf_path = make_native_pdf(docx_path)
    scanned_path = make_scanned_pdf(pdf_path)
    xlsx_path = make_xlsx()
    zip_path = make_zip(pdf_path, xlsx_path)

    for p in (docx_path, pdf_path, scanned_path, xlsx_path, zip_path):
        print(f"{p.name}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
