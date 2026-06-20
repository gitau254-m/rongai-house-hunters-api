from pydantic import BaseModel, field_validator
from uuid import UUID


class SignupRequest(BaseModel):
    full_name: str
    email: str
    phone_number: str
    password: str
    role: str = "customer"          # default role is customer

    @field_validator("password")
    @classmethod
    def password_strong_enough(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("role")
    @classmethod
    def valid_role(cls, value):
        # Public signup can only create customer or caretaker
        # admin and super_admin are NEVER created through signup
        if value not in ["customer", "caretaker"]:
            raise ValueError("Role must be customer or caretaker")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: UUID