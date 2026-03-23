import os
import requests
from functools import wraps
from flask import request, jsonify
from jose import jwt, JWTError

KEYCLOAK_URL   = os.environ.get("KEYCLOAK_URL",       "http://localhost:8080")
REALM          = os.environ.get("KEYCLOAK_REALM",     "patient-realm")
CLIENT_ID      = os.environ.get("KEYCLOAK_CLIENT_ID", "patient-client")

JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"


def get_jwks():
    """Fetch public keys from Keycloak."""
    try:
        resp = requests.get(JWKS_URL, timeout=5)
        return resp.json()
    except Exception as e:
        print(f"❌ Could not fetch JWKS: {e}")
        return None


def decode_token(token: str) -> dict:
    """Decode and validate JWT using Keycloak public key."""
    jwks = get_jwks()
    if not jwks:
        raise JWTError("JWKS unavailable")

    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        options={"verify_exp": True},
    )


def get_roles(claims: dict) -> list:
    """Extract realm roles from JWT claims."""
    return (
        claims.get("realm_access", {}).get("roles", [])
    )


def require_role(*roles):
    """Decorator: allows access only if user has one of the required roles."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing token"}), 401

            token = auth_header.split(" ")[1]
            try:
                claims = decode_token(token)
            except JWTError as e:
                return jsonify({"error": f"Invalid token: {str(e)}"}), 401

            user_roles = get_roles(claims)
            if not any(r in user_roles for r in roles):
                return jsonify({
                    "error": "Access denied",
                    "your_roles": user_roles,
                    "required_one_of": list(roles)
                }), 403

            # Pass claims into the route via flask g
            request.jwt_claims = claims
            return f(*args, **kwargs)
        return wrapper
    return decorator