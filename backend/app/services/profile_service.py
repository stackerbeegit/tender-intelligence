"""
The company profile that tenders are matched against: one
`stackerbee_profile` row plus its capabilities and past projects, edited
by admins. Every change is audited and bumps the profile's `updated_at`,
which is how stored qualification results know they are stale.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.stackerbee_capability import StackerbeeCapability
from app.models.stackerbee_experience import StackerbeeExperience
from app.models.stackerbee_profile import StackerbeeProfile
from app.models.user import User
from app.schemas.profile import (
    CapabilityCreate,
    CapabilityUpdate,
    ExperienceCreate,
    ExperienceUpdate,
    ProfileUpsert,
)
from app.services import audit_service


class ProfileNotConfiguredError(DomainError):
    pass


class DuplicateCapabilityError(DomainError):
    pass


def get_profile(db: Session) -> StackerbeeProfile | None:
    return db.query(StackerbeeProfile).order_by(StackerbeeProfile.created_at).first()


def require_profile(db: Session) -> StackerbeeProfile:
    profile = get_profile(db)
    if profile is None:
        raise ProfileNotConfiguredError("The company profile has not been set up yet")
    return profile


def _touch(profile: StackerbeeProfile) -> None:
    profile.updated_at = datetime.now(timezone.utc)


def _audit(db: Session, user: User, action: str, entity_type: str, entity_id: uuid.UUID, details: dict) -> None:
    audit_service.record(
        db, action=action, user_id=user.id, entity_type=entity_type, entity_id=str(entity_id), details=details
    )


def upsert_profile(db: Session, payload: ProfileUpsert, user: User) -> StackerbeeProfile:
    data = payload.model_dump(mode="json")
    data["net_worth_inr"] = payload.net_worth_inr
    profile = get_profile(db)
    created = profile is None
    if created:
        profile = StackerbeeProfile(**data)
        db.add(profile)
    else:
        for field, value in data.items():
            setattr(profile, field, value)
        _touch(profile)
    db.commit()
    db.refresh(profile)
    _audit(db, user, "profile.created" if created else "profile.updated", "stackerbee_profile", profile.id,
           payload.model_dump(mode="json"))
    return profile


# ---------------------------------------------------------- capabilities


def add_capability(db: Session, payload: CapabilityCreate, user: User) -> StackerbeeCapability:
    profile = require_profile(db)
    if any(cap.capability == payload.capability for cap in profile.capabilities):
        raise DuplicateCapabilityError(f"Capability '{payload.capability.value}' already exists — edit it instead")
    capability = StackerbeeCapability(profile_id=profile.id, **payload.model_dump())
    db.add(capability)
    _touch(profile)
    db.commit()
    db.refresh(capability)
    _audit(db, user, "profile.capability_added", "stackerbee_capability", capability.id,
           payload.model_dump(mode="json"))
    return capability


def update_capability(
    db: Session, capability: StackerbeeCapability, payload: CapabilityUpdate, user: User
) -> StackerbeeCapability:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(capability, field, value)
    _touch(capability.profile)
    db.commit()
    db.refresh(capability)
    _audit(db, user, "profile.capability_updated", "stackerbee_capability", capability.id,
           payload.model_dump(mode="json", exclude_unset=True))
    return capability


def delete_capability(db: Session, capability: StackerbeeCapability, user: User) -> None:
    capability_id, name = capability.id, capability.capability.value
    _touch(capability.profile)
    db.delete(capability)
    db.commit()
    _audit(db, user, "profile.capability_deleted", "stackerbee_capability", capability_id, {"capability": name})


# ------------------------------------------------------------ experience


def add_experience(db: Session, payload: ExperienceCreate, user: User) -> StackerbeeExperience:
    profile = require_profile(db)
    experience = StackerbeeExperience(profile_id=profile.id, **payload.model_dump())
    db.add(experience)
    _touch(profile)
    db.commit()
    db.refresh(experience)
    _audit(db, user, "profile.experience_added", "stackerbee_experience", experience.id,
           payload.model_dump(mode="json"))
    return experience


def update_experience(
    db: Session, experience: StackerbeeExperience, payload: ExperienceUpdate, user: User
) -> StackerbeeExperience:
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("project_name") is None:
        changes.pop("project_name", None)  # required column: ignore an explicit null
    if changes.get("customer_type") is None:
        changes.pop("customer_type", None)
    for field, value in changes.items():
        setattr(experience, field, value)
    _touch(experience.profile)
    db.commit()
    db.refresh(experience)
    _audit(db, user, "profile.experience_updated", "stackerbee_experience", experience.id,
           payload.model_dump(mode="json", exclude_unset=True))
    return experience


def delete_experience(db: Session, experience: StackerbeeExperience, user: User) -> None:
    experience_id, name = experience.id, experience.project_name
    _touch(experience.profile)
    db.delete(experience)
    db.commit()
    _audit(db, user, "profile.experience_deleted", "stackerbee_experience", experience_id, {"project_name": name})
