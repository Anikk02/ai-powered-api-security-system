from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class ProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)

class ProfileResponse(BaseModel):
    id: int
    email: EmailStr
    company_name: Optional[str] = None
    role: str
    status: str
    email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

class EmailChangeRequest(BaseModel):
    new_email: EmailStr

class EmailChangeConfirm(BaseModel):
    token: str

class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=8)

class PlanResponse(BaseModel):
    name: str
    next_renewal: Optional[datetime] = None

class MessageResponse(BaseModel):
    message: str
    success: bool = True