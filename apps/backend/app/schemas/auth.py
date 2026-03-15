from pydantic import BaseModel, Field


class AuthRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class AuthLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=16)


class AuthUserResponse(BaseModel):
    id: str
    email: str
    is_pro: bool


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class AuthLogoutResponse(BaseModel):
    ok: bool = True
