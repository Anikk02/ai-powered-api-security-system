import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.authentication.dependencies import require_active_client
from app.db.models.client import Client
from app.settings.schemas import (
    ProfileUpdate,
    ProfileResponse,
    PasswordChangeRequest,
    EmailChangeRequest,
    EmailChangeConfirm,
    AccountDeleteRequest,
    PlanResponse,
    MessageResponse
)
from app.settings.service import (
    get_profile,
    update_profile,
    change_password,
    request_email_change,
    confirm_email_change,
    delete_account,
    get_plan_info,
    logout_all_devices
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
    },
)

# ============================================================
# 1. PROFILE
# ============================================================

@router.get("/profile", response_model=ProfileResponse)
async def get_profile_endpoint(
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user profile.
    """
    return await get_profile(db, current_client.id)

@router.put("/profile", response_model=ProfileResponse)
async def update_profile_endpoint(
    profile_data: ProfileUpdate,
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user profile.
    """
    return await update_profile(
        db, 
        current_client.id, 
        profile_data.model_dump(exclude_unset=True)
    )

# ============================================================
# 2. PASSWORD
# ============================================================

@router.post("/change-password", response_model=MessageResponse)
async def change_password_endpoint(
    password_data: PasswordChangeRequest,
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user password.
    """
    await change_password(
        db,
        current_client.id,
        password_data.current_password,
        password_data.new_password
    )
    return {"message": "Password changed successfully", "success": True}

# ============================================================
# 3. EMAIL CHANGE
# ============================================================

@router.post("/request-email-change", response_model=MessageResponse)
async def request_email_change_endpoint(
    email_data: EmailChangeRequest,
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Request email change - sends verification link to new email.
    """
    await request_email_change(db, current_client.id, email_data.new_email)
    return {
        "message": "Verification email sent to your new address", 
        "success": True
    }

@router.post("/confirm-email-change", response_model=MessageResponse)
async def confirm_email_change_endpoint(
    confirm_data: EmailChangeConfirm,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm email change with token.
    """
    message = await confirm_email_change(db, confirm_data.token)
    return {"message": message, "success": True}

# ============================================================
# 4. ACCOUNT DELETION
# ============================================================

@router.delete("/account", response_model=MessageResponse)
async def delete_account_endpoint(
    delete_data: AccountDeleteRequest,
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user account.
    """
    await delete_account(db, current_client.id, delete_data.password)
    return {"message": "Account deleted successfully", "success": True}

# ============================================================
# 5. PLAN
# ============================================================

@router.get("/plan", response_model=PlanResponse)
async def get_plan_endpoint(
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current plan information.
    """
    return await get_plan_info(db, current_client.id)

# ============================================================
# 6. LOGOUT ALL DEVICES
# ============================================================

@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_endpoint(
    current_client: Client = Depends(require_active_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout from all devices.
    """
    await logout_all_devices(db, current_client.id)
    return {"message": "Logged out from all devices", "success": True}