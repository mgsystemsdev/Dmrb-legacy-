from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class BootstrapRequest(BaseModel):
    username: str
    password: str
    password_confirm: str


class UserSession(BaseModel):
    user_id: int
    username: str
    role: str
    exp: int
