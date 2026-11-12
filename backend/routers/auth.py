from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.core.dependencies import get_current_user
from backend.database import get_db
from backend.models import User

from backend.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse
)

from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# =========================================================
# REGISTER
# =========================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):

    # Normalize LeetCode username
    leetcode_username = (
        user_data.leetcode_username.strip()
        if user_data.leetcode_username
        else None
    )

    # Check whether email already exists
    normalized_email = user_data.email.strip().lower()

    existing_user = db.query(User).filter(
        User.email == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )

    # Check LeetCode username if provided
    if leetcode_username:

        existing_leetcode_user = db.query(User).filter(
            User.leetcode_username == leetcode_username
        ).first()

        if existing_leetcode_user:
            raise HTTPException(
                status_code=400,
                detail="LeetCode username already linked."
            )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create new user
    new_user = User(
        email=normalized_email,
        password_hash=hashed_password,
        leetcode_username=leetcode_username
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email or LeetCode username already registered."
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to create account."
        )

    return new_user


# =========================================================
# LOGIN
# =========================================================

@router.post(
    "/login",
    response_model=TokenResponse
)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    normalized_email = user_data.email.strip().lower()

    user = db.query(User).filter(
        User.email == normalized_email
    ).first()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    # Verify password
    if not verify_password(
        user_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    # Generate JWT
    access_token = create_access_token(
        data={
            "sub": str(user.id)
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# =========================================================
# GET CURRENT LOGGED-IN USER
# =========================================================

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user
