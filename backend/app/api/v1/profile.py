import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.stackerbee_capability import StackerbeeCapability
from app.models.stackerbee_experience import StackerbeeExperience
from app.models.user import User
from app.schemas.profile import (
    CapabilityCreate,
    CapabilityRead,
    CapabilityUpdate,
    CompanyProfileResponse,
    ExperienceCreate,
    ExperienceRead,
    ExperienceUpdate,
    ProfileRead,
    ProfileUpsert,
)
from app.services import profile_service
from app.services.profile_service import DuplicateCapabilityError, ProfileNotConfiguredError

router = APIRouter(prefix="/profile", tags=["profile"])

_PROFILE_MISSING = "Create the company profile first (PUT /profile)"


@router.get("", response_model=CompanyProfileResponse)
def get_company_profile(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Readable by every signed-in user, since qualification results are
    explained in terms of it. `profile` is null until an admin creates it."""
    profile = profile_service.get_profile(db)
    if profile is None:
        return CompanyProfileResponse(profile=None, capabilities=[], experience=[])
    return CompanyProfileResponse(
        profile=ProfileRead.model_validate(profile),
        capabilities=[CapabilityRead.model_validate(c) for c in profile.capabilities],
        experience=[ExperienceRead.model_validate(e) for e in profile.experience],
    )


@router.put("", response_model=ProfileRead)
def upsert_company_profile(
    payload: ProfileUpsert, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    """Creates the single profile row, or replaces its fields."""
    return profile_service.upsert_profile(db, payload, admin)


# ---------------------------------------------------------- capabilities


def _get_capability_or_404(db: Session, capability_id: uuid.UUID) -> StackerbeeCapability:
    capability = db.get(StackerbeeCapability, capability_id)
    if capability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Capability not found")
    return capability


@router.post("/capabilities", response_model=CapabilityRead, status_code=status.HTTP_201_CREATED)
def add_capability(
    payload: CapabilityCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    try:
        return profile_service.add_capability(db, payload, admin)
    except ProfileNotConfiguredError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_PROFILE_MISSING)
    except DuplicateCapabilityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch("/capabilities/{capability_id}", response_model=CapabilityRead)
def update_capability(
    capability_id: uuid.UUID,
    payload: CapabilityUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    return profile_service.update_capability(db, _get_capability_or_404(db, capability_id), payload, admin)


@router.delete("/capabilities/{capability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_capability(
    capability_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    profile_service.delete_capability(db, _get_capability_or_404(db, capability_id), admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ experience


def _get_experience_or_404(db: Session, experience_id: uuid.UUID) -> StackerbeeExperience:
    experience = db.get(StackerbeeExperience, experience_id)
    if experience is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Experience record not found")
    return experience


@router.post("/experience", response_model=ExperienceRead, status_code=status.HTTP_201_CREATED)
def add_experience(
    payload: ExperienceCreate, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    try:
        return profile_service.add_experience(db, payload, admin)
    except ProfileNotConfiguredError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_PROFILE_MISSING)


@router.patch("/experience/{experience_id}", response_model=ExperienceRead)
def update_experience(
    experience_id: uuid.UUID,
    payload: ExperienceUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    return profile_service.update_experience(db, _get_experience_or_404(db, experience_id), payload, admin)


@router.delete("/experience/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    experience_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))
):
    profile_service.delete_experience(db, _get_experience_or_404(db, experience_id), admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
