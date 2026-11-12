from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator
)


# =========================================================
# USER REGISTRATION
# =========================================================

class UserRegister(BaseModel):

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=72
    )

    leetcode_username: str | None = Field(
        default=None,
        min_length=1,
        max_length=50
    )

    @field_validator("leetcode_username", mode="before")
    @classmethod
    def normalize_leetcode_username(cls, value):

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value


# =========================================================
# USER LOGIN
# =========================================================

class UserLogin(BaseModel):

    email: EmailStr

    password: str


# =========================================================
# JWT TOKEN RESPONSE
# =========================================================

class TokenResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"


# =========================================================
# USER RESPONSE
# =========================================================

class UserResponse(BaseModel):

    id: int

    email: EmailStr

    leetcode_username: str | None = None

    model_config = ConfigDict(
        from_attributes=True
    )