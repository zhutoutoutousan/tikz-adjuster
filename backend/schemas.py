"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_premium: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DiagramCreate(BaseModel):
    title: str
    tikz_code: str


class DiagramResponse(BaseModel):
    id: int
    title: str
    tikz_code: str
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str

