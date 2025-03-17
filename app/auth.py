import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from keycloak.keycloak_openid import KeycloakOpenID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User

router = APIRouter()

keycloak_openid = KeycloakOpenID(
    server_url=os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080/auth/"),
    realm_name=os.getenv("KEYCLOAK_REALM", "chat_realm"),
    client_id=os.getenv("KEYCLOAK_CLIENT_ID", "chat_client"),
    verify=True,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        public_key = (
            "-----BEGIN PUBLIC KEY-----\n"
            + "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAx3V7fKMuAO055R158iL18lehMdjFOZr1P7tmvrbQK3v/9hgbB6ROhOAmT1Aj+ml7rNMb+eMeJEPvDuE5sQm9hMUAU88bWC/pqWyCIegEEWEixeItUrBZLxEsmWagF5wFc90juNxu0qXEf2r/oKuRSdWuJXRx4IRkZm24XzlTLI/z7DZUvRL3t4e/XpnLgb8dVRw/xSmrqAFnbXbRaESDpp77KhTKlhxkVBiT5rBKRwAwI3a7kEYEFtvX3wpRimGPOh/uogtbHn1wKPmFLfpcchu6eIozvWTcVPkfPPSqOwS7HyYlHUdMS+MSjKlmM9dBCh81kgxRWbXLkz0vf6dQ3QIDAQAB"
            + "\n-----END PUBLIC KEY-----"
        )
        decoded_token = jwt.decode(
            token, public_key, algorithms=["RS256"], options={"verify_aud": False}
        )
        return decoded_token
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/protected")
async def get_current_user(
    user=Depends(verify_token), db: AsyncSession = Depends(get_db)
):
    user_db = await db.execute(select(User).where(User.id == user["sub"]))
    user_db = user_db.scalar()
    if not user_db:
        user_db = User(id=user["sub"], username=user["preferred_username"])
        db.add(user_db)
    return user
