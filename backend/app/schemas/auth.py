"""Auth schemas."""

from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int
    refreshToken: str | None = None
    role: str


class LoginRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class UserRead(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
