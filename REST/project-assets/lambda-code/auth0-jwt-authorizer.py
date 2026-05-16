import os
import json
import time
import urllib.request
import base64
from urllib.error import HTTPError, URLError

try:
    import jwt
except ImportError as exc:
    raise RuntimeError(
        "PyJWT with cryptography support is required. Package this Lambda with "
        "`PyJWT[crypto]` or attach a Lambda layer that provides it."
    ) from exc


JWKS_CACHE = None
JWKS_CACHE_EXPIRES = 0
JWKS_CACHE_SECONDS = 60 * 60


def handler(event, context):
    try:
        token = extract_bearer_token(event.get("authorizationToken", ""))
        header = decode_jwt_part(token, 0)
        validate_header(header)
        claims = validate_token(token, header)
        return build_policy(
            claims.get("sub", "auth0-user"),
            "Allow",
            cellar_resource_arn(event["methodArn"]),
            claims
        )
    except Exception as exc:
        print(f"Auth0 authorizer denied request: {exc}")
        return build_policy("unauthorized", "Deny", event.get("methodArn", "*"))


def extract_bearer_token(header_value):
    if not header_value or not isinstance(header_value, str):
        raise ValueError("Missing Authorization header")

    parts = header_value.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Authorization header must use Bearer token format")

    token = parts[1].strip()
    if len(token.split(".")) != 3:
        raise ValueError("Invalid JWT format")

    return token


def decode_jwt_part(token, index):
    part = token.split(".")[index]
    padded = part + "=" * (-len(part) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid JWT encoding") from exc


def validate_header(header):
    if header.get("alg") != "RS256":
        raise ValueError("Only RS256 tokens are accepted")
    if not header.get("kid"):
        raise ValueError("JWT missing kid")


def validate_token(token, header):
    issuer = required_env("AUTH0_ISSUER")
    audience = required_env("AUTH0_AUDIENCE")
    jwks_uri = os.environ.get(
        "AUTH0_JWKS_URI",
        f"{issuer.rstrip('/')}/.well-known/jwks.json"
    )

    signing_key = get_signing_key(header["kid"], jwks_uri)
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "sub"]
            }
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("JWT expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise ValueError("Invalid audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise ValueError("Invalid issuer") from exc
    except jwt.InvalidSignatureError as exc:
        raise ValueError("Invalid JWT signature") from exc
    except jwt.PyJWTError as exc:
        raise ValueError(f"JWT validation failed: {exc}") from exc


def get_signing_key(kid, jwks_uri):
    jwks = get_jwks(jwks_uri)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

    jwks = get_jwks(jwks_uri, force_refresh=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

    raise ValueError("Matching JWKS key not found")


def get_jwks(jwks_uri, force_refresh=False):
    global JWKS_CACHE, JWKS_CACHE_EXPIRES
    now = int(time.time())
    if not force_refresh and JWKS_CACHE and JWKS_CACHE_EXPIRES > now:
        return JWKS_CACHE

    JWKS_CACHE = fetch_json(jwks_uri)
    JWKS_CACHE_EXPIRES = now + JWKS_CACHE_SECONDS
    return JWKS_CACHE


def fetch_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"JWKS request failed with status {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"JWKS request failed with status {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"JWKS request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("JWKS response was not valid JSON") from exc


def cellar_resource_arn(method_arn):
    # arn:aws:execute-api:region:account-id:api-id/stage/verb/resource/path
    arn_parts = method_arn.split(":")
    resource_parts = arn_parts[5].split("/")
    api_id = resource_parts[0]
    stage = resource_parts[1]
    return ":".join(arn_parts[:5]) + f":{api_id}/{stage}/*/cellar/*"


def build_policy(principal_id, effect, resource, claims=None):
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }

    if claims:
        policy["context"] = {
            "sub": string_context(claims.get("sub")),
            "scope": string_context(claims.get("scope")),
            "iss": string_context(claims.get("iss")),
            "aud": string_context(claims.get("aud"))
        }

    return policy


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def string_context(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


lambda_handler = handler
