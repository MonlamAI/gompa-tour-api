from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from prisma import Prisma
from model.enum import Role
from Config.connection import get_db
from lib.require_api_key import require_api_key

router = APIRouter()


# Pydantic models for request & response validation
class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: Optional[Role] = Role.USER

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[Role] = None

class UserResponse(UserBase):
    id: str

    class Config:
        from_attributes = True

# Create a new user

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Prisma = Depends(get_db)):
    try:
        # Check if the user already exists by email
        existing_user = await db.user.find_unique(where={"email": user.email})
        
        if existing_user:
            return existing_user

        new_user = await db.user.create(
            data={
                "username": user.username,
                "email": user.email,
                "role": Role.USER,
            }
        )
        return new_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get all users
@router.get("/", response_model=List[UserResponse], dependencies=[Depends(require_api_key)])
async def get_users(db: Prisma = Depends(get_db)):
    users = await db.user.find_many()
    return users

# Get a specific user by ID
@router.get("/{user_email}", response_model=UserResponse, dependencies=[Depends(require_api_key)])
async def get_user(user_email: str, db: Prisma = Depends(get_db)):
    user = await db.user.find_unique(where={"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Update a user
@router.put("/{user_email}", response_model=UserResponse, dependencies=[Depends(require_api_key)])
async def update_user(user_email: str, user: UserUpdate, db: Prisma = Depends(get_db)):
    existing_user = await db.user.find_unique(where={"email": user_email})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await db.user.update(
        where={"email": user_email},
        data=user.dict(exclude_unset=True),
    )
    return updated_user

# Delete a user
@router.delete("/{user_email}", dependencies=[Depends(require_api_key)])
async def delete_user(user_email: str, db: Prisma = Depends(get_db)):
    user = await db.user.find_unique(where={"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.user.delete(where={"email": user_email})
    return {"message": "User deleted successfully"}
