from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.user.assign_sensors import AssignSensors
from app.application.user.create_user import CreateUser
from app.application.user.update_user import UpdateUser
from app.domain.audit.entities import ActionType
from app.infrastructure.api.dependencies import get_current_session
from app.infrastructure.api.middleware.audit import audit_action
from app.infrastructure.api.middleware.auth import require_role, TokenData
from app.infrastructure.database.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["Users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str
    phone: str | None = None


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    role: str | None = None
    phone: str | None = None
    status: str | None = None


class AssignSensorsRequest(BaseModel):
    sensor_ids: list[UUID]


@router.post("", dependencies=[Depends(require_role("admin"))])
@audit_action(action_type=ActionType.USER_CREATED, resource_type="user")
async def create_user(
    request: Request,
    create_request: CreateUserRequest,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    use_case = CreateUser(repo)

    try:
        result = await use_case.execute(
            email=create_request.email,
            password=create_request.password,
            full_name=create_request.full_name,
            role=create_request.role,
            phone=create_request.phone,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", dependencies=[Depends(require_role("admin"))])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    users = await repo.list_all(skip=skip, limit=limit)

    return [
        {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "status": user.status.value,
            "created_at": user.created_at.isoformat(),
        }
        for user in users
    ]


@router.get("/{user_id}", dependencies=[Depends(require_role("admin"))])
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "phone": user.phone,
        "status": user.status.value,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


@router.put("/{user_id}", dependencies=[Depends(require_role("admin"))])
@audit_action(action_type=ActionType.USER_UPDATED, resource_type="user")
async def update_user(
    request: Request,
    user_id: UUID,
    update_request: UpdateUserRequest,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    use_case = UpdateUser(repo)

    try:
        result = await use_case.execute(
            user_id=user_id,
            email=update_request.email,
            password=update_request.password,
            full_name=update_request.full_name,
            role=update_request.role,
            phone=update_request.phone,
            status=update_request.status,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{user_id}", dependencies=[Depends(require_role("admin"))])
@audit_action(action_type=ActionType.USER_DELETED, resource_type="user")
async def delete_user(
    request: Request,
    user_id: UUID,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    deleted = await repo.delete(user_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return {"message": "User deleted successfully"}


@router.put("/{user_id}/sensors", dependencies=[Depends(require_role("admin"))])
@audit_action(action_type=ActionType.CONFIG_UPDATED, resource_type="user_sensor_assignment")
async def assign_sensors_to_user(
    request: Request,
    user_id: UUID,
    assign_request: AssignSensorsRequest,
    session: AsyncSession = Depends(get_current_session),
):
    repo = UserRepository(session)
    use_case = AssignSensors(repo)

    try:
        result = await use_case.execute(user_id, assign_request.sensor_ids)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
