"""
Firebase Authentication Integration

Provides FastAPI dependencies for verifying Firebase ID tokens.
"""

import os
from typing import Optional
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth

security = HTTPBearer()

# Initialize Firebase Admin SDK
def init_firebase():
    # Only initialize if not already initialized
    if not firebase_admin._apps:
        # Priority 1: Environment variable (JSON string)
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if service_account_json:
            try:
                import json
                cred_dict = json.loads(service_account_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin initialized via environment variable.")
                return
            except Exception as e:
                print(f"⚠️ Failed to initialize Firebase Admin from env var: {e}")

        # Priority 2: File path
        cred_path = os.getenv("FIREBASE_CREDENTIALS", "backend/secrets/firebase-admin.json")
        try:
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin initialized via file.")
            else:
                print(f"⚠️ Firebase Admin credentials not found at {cred_path} and FIREBASE_SERVICE_ACCOUNT is unset. Authentication will fail.")
        except Exception as e:
            print(f"⚠️ Failed to initialize Firebase Admin from file: {e}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify the Firebase ID token and return the decoded user payload.
    Raises 401 Unauthorized if token is missing or invalid.
    """
    token = credentials.credentials
    try:
        # Verify the token using Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        # Extract relevant user info (uid, email, etc.)
        user_info = {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture")
        }
        print(f"🔑 API Request from: {user_info['email']}")
        return user_info
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_optional_user(request: Request) -> Optional[dict]:
    """
    Optional authentication. Returns user info if valid token is provided, 
    otherwise returns None. Never raises 401.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name")
        }
    except:
        return None
