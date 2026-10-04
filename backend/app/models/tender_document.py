import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import DocumentType, ExtractionStatus, OcrStatus


class TenderDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Document metadata. `source_url` is populated by a connector/manual
    entry at ingestion time; `storage_path`/`checksum_sha256`/
    `file_size_bytes`/`page_count`/`extracted_text` and the OCR/extraction
    status stay null until the Sprint 3 document processing pipeline
    (`app/services/document_processing_service.py`) downloads/validates/
    extracts the file.
    """

    __tablename__ = "tender_documents"

    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        sa_enum(DocumentType), nullable=False, default=DocumentType.OTHER
    )
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ocr_status: Mapped[OcrStatus] = mapped_column(sa_enum(OcrStatus), nullable=False, default=OcrStatus.NOT_REQUIRED)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        sa_enum(ExtractionStatus), nullable=False, default=ExtractionStatus.PENDING
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tender: Mapped["Tender"] = relationship(back_populates="documents")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderDocument {self.file_name}>"
