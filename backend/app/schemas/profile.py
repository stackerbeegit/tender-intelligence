import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CustomerType, TenderCategory


def _clean_names(values: list[str]) -> list[str]:
    """Trimmed, non-empty, de-duplicated (case-insensitively), order kept."""
    seen: set[str] = set()
    cleaned = []
    for value in values:
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            cleaned.append(value)
    return cleaned


class TurnoverYear(BaseModel):
    financial_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2024-25"])
    amount_inr: float = Field(ge=0)


class ProfileUpsert(BaseModel):
    """Leave a field null when it isn't known — the matching engine then
    reports UNKNOWN instead of guessing. `msme_registered=false` asserts
    the company is *not* registered; null means "not recorded"."""

    company_name: str = Field(min_length=1, max_length=255)
    msme_registered: bool | None = None
    msme_certificate_ref: str | None = Field(default=None, max_length=255)
    startup_registered: bool | None = None
    startup_certificate_ref: str | None = Field(default=None, max_length=255)
    turnover_by_year: list[TurnoverYear] = []
    net_worth_inr: Decimal | None = None
    years_in_business: int | None = Field(default=None, ge=0)
    employee_count: int | None = Field(default=None, ge=0)
    locations: list[str] = []
    certifications: list[str] = []

    @field_validator("turnover_by_year")
    @classmethod
    def _unique_years(cls, years: list[TurnoverYear]) -> list[TurnoverYear]:
        labels = [y.financial_year for y in years]
        if len(labels) != len(set(labels)):
            raise ValueError("each financial year may appear only once")
        return sorted(years, key=lambda y: y.financial_year, reverse=True)

    @field_validator("locations", "certifications")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return _clean_names(values)


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    msme_registered: bool | None
    msme_certificate_ref: str | None
    startup_registered: bool | None
    startup_certificate_ref: str | None
    turnover_by_year: list[TurnoverYear]
    net_worth_inr: Decimal | None
    years_in_business: int | None
    employee_count: int | None
    locations: list[str]
    certifications: list[str]
    updated_at: datetime


class CapabilityCreate(BaseModel):
    capability: TenderCategory
    technologies: list[str] = []
    certifications: list[str] = []
    description: str | None = None

    @field_validator("technologies", "certifications")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return _clean_names(values)


class CapabilityUpdate(BaseModel):
    technologies: list[str] | None = None
    certifications: list[str] | None = None
    description: str | None = None

    @field_validator("technologies", "certifications")
    @classmethod
    def _clean(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_names(values)


class CapabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    capability: TenderCategory
    technologies: list[str]
    certifications: list[str]
    description: str | None


class ExperienceCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=500)
    client_name: str | None = Field(default=None, max_length=255)
    customer_type: CustomerType
    capability: TenderCategory | None = None
    industry: str | None = Field(default=None, max_length=255)
    technologies: list[str] = []
    project_value_inr: Decimal | None = Field(default=None, ge=0)
    year: int | None = Field(default=None, ge=1950, le=2100)
    description: str | None = None

    @field_validator("technologies")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return _clean_names(values)


class ExperienceUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=500)
    client_name: str | None = Field(default=None, max_length=255)
    customer_type: CustomerType | None = None
    capability: TenderCategory | None = None
    industry: str | None = Field(default=None, max_length=255)
    technologies: list[str] | None = None
    project_value_inr: Decimal | None = Field(default=None, ge=0)
    year: int | None = Field(default=None, ge=1950, le=2100)
    description: str | None = None

    @field_validator("technologies")
    @classmethod
    def _clean(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _clean_names(values)


class ExperienceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_name: str
    client_name: str | None
    customer_type: CustomerType
    capability: TenderCategory | None
    industry: str | None
    technologies: list[str]
    project_value_inr: Decimal | None
    year: int | None
    description: str | None


class CompanyProfileResponse(BaseModel):
    profile: ProfileRead | None
    capabilities: list[CapabilityRead]
    experience: list[ExperienceRead]
