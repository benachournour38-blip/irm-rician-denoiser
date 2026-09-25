from fastapi import APIRouter, HTTPException, Header, Request, Depends
from pydantic import BaseModel
from typing import Optional
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

class LoginRequest(BaseModel):
    password: str

def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = None
):
    """Dépendance FastAPI pour valider l'accès sécurisé à chaque requête."""
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split("Bearer ", 1)[1].strip()
    elif token:
        auth_token = token.strip()

    if not auth_token:
        raise HTTPException(status_code=401, detail="Accès restreint. Veuillez vous connecter.")

    user = AuthService.validate_token(auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expirée ou mot de passe invalide.")
    return user

@router.post("/login")
def login(req: LoginRequest):
    user = AuthService.verify_password(req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect. Accès refusé.")
    
    token = AuthService.create_token(user)
    return {
        "success": True,
        "token": token,
        "user": user,
        "message": f"Bienvenue, {user['username']}"
    }

@router.get("/me")
def verify_session(user: dict = Depends(get_current_user)):
    return {
        "authenticated": True,
        "user": user
    }

@router.post("/logout")
def logout():
    return {
        "success": True,
        "message": "Déconnexion réussie."
    }
