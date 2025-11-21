import time
import uuid

import sqlite3
from fastapi import APIRouter, HTTPException, Depends, Request

from state import get_db, limiter
from models.auth import LoginModel, RegisterModel
from authentication.password import hash_password, verify_password
from authentication.jwt import create_token, user_key

router = APIRouter()

ACCESS_TOKEN_EXPIRE = 600        # 10 min
REFRESH_TOKEN_EXPIRE = 3600 * 24 # 1 day

#register endpoint
@router.post("/register")
@limiter.limit("10/minute", key_func=user_key)
def register_user(request: Request, body: RegisterModel, conn=Depends(get_db)):
    cursor = conn.cursor()

    hashed_pwd = hash_password(body.password)
    
    # Generate a UUID for the new user
    user_id = str(uuid.uuid4())

    try:
        cursor.execute(
            "INSERT INTO users (id, email, password, admin) VALUES (?, ?, ?, ?)",
            (user_id, body.email, hashed_pwd, False)
        )
        conn.commit()
        
        access_token = create_token({"user_id": user_id, "admin": False}, ACCESS_TOKEN_EXPIRE)
        refresh_token = create_token({"user_id": user_id,  "admin": False}, REFRESH_TOKEN_EXPIRE)
        
        cursor.execute(
            "UPDATE users SET access_token=?, refresh_token=?, access_exp=?, refresh_exp=? WHERE id=?",
            (access_token, refresh_token,
             int(time.time()) + ACCESS_TOKEN_EXPIRE,
             int(time.time()) + REFRESH_TOKEN_EXPIRE,
             user_id)
        )
        conn.commit()
        
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already registered")

    return {"access_token": access_token, "refresh_token": refresh_token}

#login endpoint
@router.post("/login")
@limiter.limit("10/minute", key_func=user_key)
def login_user(request: Request, body: LoginModel, conn=Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT id, password, admin, refresh_token, refresh_exp FROM users WHERE email=?", (body.email,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=400, detail="User not found")

    user_id, hashed_pwd, admin, _, refresh_exp = row

    # validate password
    if not verify_password(body.password, hashed_pwd):
        raise HTTPException(status_code=401, detail="Invalid password")

    now = int(time.time())
    if refresh_exp > now:
        # refresh valid -> reuse it, just issue new access_token
        new_access = create_token({"user_id": user_id, "admin": admin}, ACCESS_TOKEN_EXPIRE)
        cursor.execute(
            "UPDATE users SET access_token=?, access_exp=? WHERE id=?",
            (new_access, now + ACCESS_TOKEN_EXPIRE, user_id)
        )
        conn.commit()
        return {"access_token": new_access}
    else:
        # refresh expired -> create new pair
        new_access = create_token({"user_id": user_id, "admin": admin}, ACCESS_TOKEN_EXPIRE)
        new_refresh = create_token({"user_id": user_id, "admin": admin}, REFRESH_TOKEN_EXPIRE)
        cursor.execute(
            "UPDATE users SET access_token=?, refresh_token=?, access_exp=?, refresh_exp=? WHERE id=?",
            (new_access, new_refresh, now + ACCESS_TOKEN_EXPIRE, now + REFRESH_TOKEN_EXPIRE, user_id)
        )
        conn.commit()
        return {"access_token": new_access, "refresh_token": new_refresh}

