# Tawny Port - REST API Console Runbook

## Purpose

Build the Tawny Port REST API deployment in the AWS Console, then validate the browser user experience through Cognito Managed Login.

### Details

Deployment details:

- DynamoDB session table
- Auth0 machine-to-machine access for Cellar routes
- Cognito Hosted UI login with server-side token exchange
- Lambda route handlers for Table, Chalice, and Cellar
- API Gateway REST API routes, integrations, and authorizer placement
- IAM permissions, Lambda environment variables, route tests, and browser login validation


## Prerequisites

### Dependencies

#### Applications

| Dependency | Requirement |
| --- | --- |
| AWS Console and browser | Create resources visually and complete browser-based login or validation steps. |
| AWS CLI | Create, update, describe, validate, and tear down AWS resources. |
| jq | Parse JSON responses and export generated IDs, tokens, or ARNs. |
| Python 3 | Run helper scripts and package Python-based Lambda code when required. |
| zip | Package Lambda source files for upload. |
| curl | Validate API routes and HTTP responses. |

#### Infrastructure

| Dependency | Requirement |
| --- | --- |
| AWS account and region | Create the Tawny Port REST API deployment in the intended account and region. |
| DynamoDB | Create the session table used by browser-backed Chalice routes. |
| Lambda and IAM | Create route handlers, execution roles, environment variables, and permissions. |

#### Access Requirements

| Dependency | Requirement |
| --- | --- |
| AWS credentials | Use credentials with permission to manage API Gateway, Lambda, IAM, Cognito, DynamoDB, and CloudWatch. |
| Auth0 tenant access | Create or reuse an Auth0 API and obtain M2M tokens for Cellar route validation. |
| Cognito access | Create or configure the user pool, app client, hosted domain, managed login, callback URL, and logout URL. |

#### APIs And Services

| Dependency | Requirement |
| --- | --- |
| API Gateway REST API | Create routes, integrations, stages, and authorizer placement for this deployment. |
| Amazon Cognito | Host browser login and complete server-side token exchange. |
| Auth0 | Protect Cellar routes with machine-to-machine access. |
| DynamoDB | Store short-lived `sessionId` records for Chalice routes. |
| CloudWatch Logs | Validate Lambda execution and troubleshoot route behavior. |

### Supporting Files

| File | Use |
| --- | --- |
| [`../env.example`](../env.example) | Deployment value template copied to `.env` before building. |
| [`../README.md`](../README.md) | REST API deployment overview and document map. |
| [`architecture.md`](architecture.md) | Request-flow, route-boundary, and implementation reference. |
| [`RUNBOOK-CLI.md`](RUNBOOK-CLI.md) | Companion runbook for the same architecture. |
| [`../project-assets/lambda-code/`](../project-assets/lambda-code/) | Lambda source files used by this deployment. |
| [`../project-assets/lambda-code/README.md`](../project-assets/lambda-code/README.md) | Lambda upload and Auth0 authorizer packaging guide. |
| [`../../shared/tawny-port-brand/`](../../shared/tawny-port-brand/) | Cognito Managed Login brand assets. |
| [`../../shared/tawny-port-brand/brand-identity.md`](../../shared/tawny-port-brand/brand-identity.md) | Color and type reference for managed login branding. |

### Deployment Model

Tawny Port uses route domains as trust boundaries. The stage stays environmental (`prod`), while the route domain determines the access model.

| Domain | Route pattern | Auth model | Purpose |
| --- | --- | --- | --- |
| Cellar | `/prod/cellar/*` | Auth0 machine-to-machine bearer token | Internal developer and service access |
| Table | `/prod/table/*` | Public routes plus Cognito Hosted UI | Browser entry, login callback, and logout |
| Chalice | `/prod/chalice/*` | Lambda validates `sessionId` against DynamoDB | Authenticated browser routes |

> [!WARNING]
> Keep Auth0 authorization scoped to Cellar. Table and Chalice depend on Cognito authorization-code flow, HttpOnly cookies, and DynamoDB session validation.

### Prepare Deployment Values

Copy the environment template before starting. Use it as the working record for planned values and resource outputs.

```bash
cp REST/env.example REST/.env
source REST/.env
```
---

# Session Store And Identity Providers

## 1. Create The DynamoDB Session Table

Create the session table first. Lambda environment variables and IAM policies refer to this table, so getting it in place early keeps the later setup clean.

1. Open **AWS Console**.
2. Go to **DynamoDB**.
3. Create a table.
4. Configure:

| Field | Value |
| --- | --- |
| Table name | `tawny-port-sessions` |
| Partition key | `sessionId` |
| Partition key type | `String` |
| Sort key | None |
| Capacity mode | On-demand |
| TTL attribute | `expiresAt` |

> [!IMPORTANT]
> Use `sessionId` exactly as the partition key. The callback, sipper, and logout Lambdas all read or write sessions by that key.

> [!IMPORTANT]
> Keep these values handy for Lambda environment variables, IAM policies, and session validation:

| Parameter | Console Location | Value |
| --- | --- | --- |
| Table name | DynamoDB table details | `tawny-port-sessions` |
| Partition key | Table schema | `sessionId` |
| TTL attribute | Table TTL settings | `expiresAt` |
| Table ARN | DynamoDB table details | `arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions` |

Session item shape:

```json
{
  "sessionId": "<SESSION_ID>",
  "userEmail": "user@example.com",
  "userName": "USER",
  "expiresAt": 1770000000
}
```

Use stable table settings for the session store, and update only the deployment-specific identifiers.

| Category | Value |
| --- | --- |
| Table purpose | Browser session store |
| Partition key | `sessionId` |
| TTL attribute | `expiresAt` |
| Deployment-specific values | AWS region, AWS account ID in IAM policies, optional session expiration duration in Lambda code |

### DynamoDB Session Settings

`tawny-port-sessions` is not a user database. It is a short-lived browser session table created after Cognito authentication succeeds.

The callback Lambda writes:

```text
sessionId -> opaque random UUID stored in an HttpOnly cookie
userEmail -> extracted from Cognito ID token claims
userName  -> extracted from Cognito username or email fallback
expiresAt -> TTL epoch seconds
```

The sipper Lambdas only trust the session after a DynamoDB `GetItem` succeeds. This keeps Cognito tokens out of browser-exposed application routes and keeps the Chalice layer simple.


## 2. Configure Auth0 For Cellar Routes

Use Auth0 only for Cellar. These routes are for developer and service access, so the flow is machine-to-machine instead of browser login.

1. Open the Auth0 dashboard.
2. Create or confirm the Tawny Port API.
3. Create or confirm the machine-to-machine application.
4. Authorize the M2M application for the Tawny Port API.

| Field | Value |
| --- | --- |
| Auth0 API name | `Tawny Port API` |
| API audience | `<AUTH0_AUDIENCE>` |
| Signing algorithm | `RS256` |
| M2M app purpose | Cellar developer/API access |

> [!IMPORTANT]
> Keep these values handy for Auth0 token requests and Cellar authorizer configuration:

| Parameter | Console Location | Value |
| --- | --- | --- |
| Auth0 issuer | Auth0 application or tenant settings | `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/` |
| Auth0 API audience | Auth0 API identifier | `<AUTH0_AUDIENCE>` |
| M2M client ID | Auth0 machine-to-machine application settings | `<AUTH0_M2M_CLIENT_ID>` |
| M2M client secret | Auth0 machine-to-machine application settings | `<AUTH0_M2M_CLIENT_SECRET>` |

Treat the Auth0 API identifier as the trust anchor for Cellar. The M2M application requests a token for that exact audience, and API Gateway validates the same audience before allowing `/cellar/*` traffic through.

> [!WARNING]
> Do not use the Auth0 Management API audience, such as `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/api/v2/`, unless the route is intentionally calling Auth0 management APIs. Tawny Port Cellar routes should use the custom Tawny Port API audience you created for this application.

Use this authorizer configuration later in API Gateway:

| API Gateway authorizer field | Value |
| --- | --- |
| Name | `tawny-port-auth0-jwt` |
| REST API authorizer type | Lambda |
| Lambda event payload | Token |
| Lambda function | `auth0-jwt-authorizer` |
| Token source | `Authorization` |
| Token validation regex | `^Bearer [-0-9a-zA-Z._]*$` |
| Authorizer caching | `0` while testing, `300` after validation |

Keep Auth0 scoped to the Cellar route family and update only the identity-provider values that come from your Auth0 tenant.

| Category | Value |
| --- | --- |
| Protected routes | `/cellar/*` only |
| Authorization header | `Authorization: Bearer <TOKEN>` |
| Authorizer name | `tawny-port-auth0-jwt` |
| REST validation Lambda | `auth0-jwt-authorizer` validates issuer, audience, signature, and expiration |
| Deployment-specific values | Auth0 tenant, issuer URL, API audience, and M2M application credentials |

### Auth0 Token Validation

Validate Auth0 before moving into the Cognito browser flow. This confirms the internal Cellar path works independently from Table and Chalice.

```text
Auth0 -> Cellar -> Protected Internal Validation
Cognito -> Table -> Consumer Login
Chalice -> Session/User Experience
```

Set local shell variables for the deployment:

```bash
export AUTH0_DOMAIN="https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com"
export AUTH0_CLIENT_ID="<AUTH0_M2M_CLIENT_ID>"
export AUTH0_CLIENT_SECRET="<AUTH0_M2M_CLIENT_SECRET>"
export AUTH0_AUDIENCE="<AUTH0_AUDIENCE>"
```

Request an Auth0 access token and keep the full response temporarily:

```bash
export AUTH0_TOKEN_RESPONSE=$(curl -s --request POST \
  --url "$AUTH0_DOMAIN/oauth/token" \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"'"$AUTH0_CLIENT_ID"'",
    "client_secret":"'"$AUTH0_CLIENT_SECRET"'",
    "audience":"'"$AUTH0_AUDIENCE"'",
    "grant_type":"client_credentials"
}')
```

If you are testing without shell variables, use the direct placeholder form:

```bash
curl --request POST \
  --url https://YOUR_AUTH0_DOMAIN/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"YOUR_CLIENT_ID",
    "client_secret":"YOUR_CLIENT_SECRET",
    "audience":"YOUR_API_IDENTIFIER",
    "grant_type":"client_credentials"
}'
```

The response includes `access_token`, `scope`, `expires_in`, and `token_type`.

Inspect the response without printing the token:

```bash
echo "$AUTH0_TOKEN_RESPONSE" | jq '{token_type, expires_in, scope}'
```

Export only the raw JWT for reuse:

```bash
export AUTH0_TOKEN=$(echo "$AUTH0_TOKEN_RESPONSE" | jq -r '.access_token')
```

If you are pasting manually instead, use:

```bash
export AUTH0_TOKEN="PASTE_TOKEN_HERE"
```

For one-command refresh during local testing, request and extract the token in one step:

```bash
export AUTH0_TOKEN=$(curl -s --request POST \
  --url "$AUTH0_DOMAIN/oauth/token" \
  --header 'content-type: application/json' \
  --data '{"client_id":"'"$AUTH0_CLIENT_ID"'","client_secret":"'"$AUTH0_CLIENT_SECRET"'","audience":"'"$AUTH0_AUDIENCE"'","grant_type":"client_credentials"}' \
  | jq -r '.access_token')
```

Validate that the exported value is a JWT, not raw JSON:

```bash
echo "$AUTH0_TOKEN" | head -c 20
echo "$AUTH0_TOKEN" | awk -F '.' '{print NF}'
```

Expected shape:

```text
eyJ...
3
```

> [!WARNING]
> A common failure is storing the full JSON response, such as `{"access_token":"..."}`, instead of the raw JWT. API Gateway then reports token parsing errors such as `invalid_token` or base64 decode failures. Use `jq -r '.access_token'` to extract only the token.

Inspect the JWT payload when issuer or audience behavior is unclear:

```bash
python3 - <<'PY'
import base64
import json
import os

token = os.environ["AUTH0_TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print(json.dumps({
    "iss": claims.get("iss"),
    "aud": claims.get("aud"),
    "gty": claims.get("gty"),
    "azp": claims.get("azp"),
    "scope": claims.get("scope"),
    "exp": claims.get("exp"),
}, indent=2))
PY
```

Confirm:

- `iss` matches the Auth0 issuer configured in the authorizer Lambda environment.
- `aud` matches the custom Tawny Port API audience.
- `gty` is `client-credentials`.
- `azp` matches the M2M application client ID.

Test the protected Python Cellar route with the bearer token:

```bash
curl -H "Authorization: Bearer $AUTH0_TOKEN" \
"https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/python-cask?name=AuthTester"
```

Test the Node Cellar route the same way:

```bash
curl -H "Authorization: Bearer $AUTH0_TOKEN" \
"https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/node-barrel?name=AuthTester"
```

Expected result:

- API Gateway accepts the bearer token.
- The Cellar Lambda returns a successful response.
- CloudWatch logs show the Cellar Lambda invocation.
- The `name=AuthTester` query string appears in the Cellar Lambda event.

Test the protected route without a token:

```bash
curl -i "https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/python-cask"
```

Expected result:

- API Gateway returns `401` or `403`.
- The Cellar Lambda should not run for a missing or rejected token.

Common Auth0 validation failures:

| Failure | Likely cause | Fix |
| --- | --- | --- |
| Missing token | `Authorization` header is absent or empty | Send `Authorization: Bearer $AUTH0_TOKEN` |
| Invalid audience | Auth0 API identifier does not match the authorizer audience | Set `AUTH0_AUDIENCE` to the API identifier used by the API Gateway authorizer |
| Management API audience | Token `aud` is `https://<AUTH0_DOMAIN>/api/v2/` instead of the Tawny Port API audience | Request the token with the custom Tawny Port API identifier |
| Wrong issuer | Auth0 domain or trailing slash differs from the authorizer issuer | Match `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/` exactly |
| Expired token | `exp` is older than the current time | Request a fresh token and re-export `AUTH0_TOKEN` |
| Incorrect scopes | API requires scopes that the M2M app was not granted | Authorize the M2M app for the API scopes, then request a new token |
| Full JSON exported | `AUTH0_TOKEN` contains the whole token response instead of the JWT | Re-export with `jq -r '.access_token'` |

### Auth0 Secret Handling

- Store Auth0 secrets in a local `.env`, CI secret store, or secret manager.
- Rotate M2M client secrets.
- Use separate M2M apps for local dev, CI, and admin workflows when scopes mature.
- Do not use the Auth0 Management API audience unless the route is intentionally calling Auth0 management APIs.
- Keep Auth0 on Cellar routes only.


## 3. Configure Cognito For Browser Login

Cognito owns the browser sign-in step. The application only accepts the user after Cognito redirects back to the Table callback and the callback creates a local session.

Cognito returns an authorization code to the Table callback. The callback must exchange that code server-side before the user enters the Chalice experience.

### 3.1 Create Or Confirm User Pool

1. Open **Amazon Cognito**.
2. Create or open the user pool.
3. Configure:

| Field | Value |
| --- | --- |
| User pool name | `tawny-port-sippers` |
| Sign-in identifiers | Email, phone number, username |
| Self registration | Enabled |
| Required attributes | `birthday`, `email` |

> [!IMPORTANT]
> Keep these values handy for Cognito Hosted UI URLs, Lambda environment variables, and future authorizer comparisons:

| Parameter | Console Location | Value |
| --- | --- | --- |
| User pool name | Cognito user pool details | `tawny-port-sippers` |
| User pool ID | Cognito user pool details | `<COGNITO_USER_POOL_ID>` |
| AWS region | AWS Console region selector | `<AWS_REGION>` |

### 3.2 Create Or Confirm App Client

1. In the user pool, go to **App integration**.
2. Create or open the app client.
3. Configure:

| Field | Value |
| --- | --- |
| App client name | `port-connoisseur` |
| App type | Traditional web application / confidential client |
| Client secret | Generated and stored only in Lambda configuration or Secrets Manager |
| OAuth grant | Authorization code grant |
| Scopes | `openid`, `email`, `phone` |

> [!IMPORTANT]
> Keep these values handy for Sommelier login URLs, callback token exchange, and Lambda environment variables:

| Parameter | Console Location | Value |
| --- | --- | --- |
| App client name | Cognito app client details | `port-connoisseur` |
| Client ID | Cognito app client details | `<COGNITO_APP_CLIENT_ID>` |
| Client secret | Cognito app client details, show client secret | `<COGNITO_CLIENT_SECRET>` |
| OAuth grant | App client managed login settings | Authorization code grant |
| Scopes | App client managed login settings | `openid`, `email`, `phone` |

Use these sanitized URL patterns:

| Cognito URL field | Value |
| --- | --- |
| Allowed callback URL | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/auth/callback` |
| Allowed sign-out URL | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier` |

> [!WARNING]
> Cognito redirect and sign-out URLs must match exactly, including stage and path. A small mismatch sends users into redirect errors before Lambda code runs.

### 3.3 Configure Hosted UI Domain

Use the hosted UI domain in this shape:

```text
<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com
```

The Sommelier Lambda builds Cognito login URLs with this domain:

```text
https://<COGNITO_DOMAIN>/login?client_id=<COGNITO_APP_CLIENT_ID>&response_type=code&scope=openid+email+phone&redirect_uri=<CALLBACK_REDIRECT_URI>&state=<TARGET>
```

> [!IMPORTANT]
> Keep these values handy for `sommelier`, `auth-callback`, and `cognito-logout` environment variables:

| Parameter | Console Location | Value |
| --- | --- | --- |
| Domain prefix | Cognito domain settings | `<COGNITO_DOMAIN_PREFIX>` |
| Hosted UI domain | Cognito domain settings | `<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com` |
| Hosted UI login base | Cognito managed login URL | `https://<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com/login` |

### 3.4 Callback URL And Session Flow

The Sommelier Lambda must send users to Cognito with the Table callback as the `redirect_uri`. It must not point Cognito directly at a Chalice sipper route.

Correct flow:

```text
/prod/table/sommelier
    -> Cognito Hosted UI
    -> /prod/table/auth/callback?code=<AUTHORIZATION_CODE>&state=<TARGET>:<CSRF>
    -> Cognito /oauth2/token
    -> DynamoDB session
    -> /prod/chalice/python-sipper or /prod/chalice/node-sipper
```

Callback requirements:

- The callback Lambda is the confidential backend component that can hold `CLIENT_SECRET`.
- The callback validates CSRF state before token exchange.
- The callback exchanges the authorization code for Cognito tokens at `/oauth2/token`.
- The callback creates the short-lived DynamoDB session.
- Chalice routes receive only an HttpOnly `sessionId` cookie, not raw Cognito tokens.

> [!IMPORTANT]
> Keep `CLIENT_SECRET` off `sommelier`, browser code, and sipper Lambdas. In this architecture, only `auth-callback` is the confidential OAuth client.


### 3.5 Configure Managed Login Branding

Use the Tawny Port brand assets and quick sheet when styling Cognito Managed Login:

- [`shared/tawny-port-brand/`](../../shared/tawny-port-brand/)
- [`shared/tawny-port-brand/brand-identity.md`](../../shared/tawny-port-brand/brand-identity.md)

> [!NOTE]
> Select the asset version that meets AWS Cognito file size requirements before uploading.

Branding should support the existing browser login path. Keep these routing decisions consistent across rebuilds:

| Setting | Value |
| --- | --- |
| Browser sign-in owner | Cognito Managed Login |
| App client name | `port-connoisseur` |
| Callback path | `/prod/table/auth/callback` |
| Sign-out return path | `/prod/table/sommelier` |

Update the deployment-specific values when you rebuild or move the API:

| Value | Where it changes |
| --- | --- |
| Cognito hosted domain | Cognito domain and login URLs |
| User pool ID | Cognito configuration and Lambda environment variables |
| App client ID | Cognito login URL and Lambda environment variables |
| App client secret | `auth-callback` environment variable or secret store |
| Full callback URL | Cognito app client callback URL and `REDIRECT_URI` |
| Full logout URL | Cognito app client sign-out URL and logout redirect settings |


---

# Lambda Application Layer

## 4. Create Lambda Functions

Create one Lambda per route handler using the source files in [`project-assets/lambda-code/`](../project-assets/lambda-code/). This keeps each access pattern small and easy to troubleshoot in the console.

> [!NOTE]
> See [`project-assets/lambda-code/README.md`](../project-assets/lambda-code/README.md) for the short packaging guide, including how to build the Auth0 authorizer ZIP with PyJWT.

| Lambda function | Runtime | Source file | Handler | Purpose |
| --- | --- | --- | --- | --- |
| `auth0-jwt-authorizer` | Python | [`auth0-jwt-authorizer.py`](../project-assets/lambda-code/auth0-jwt-authorizer.py) | `lambda_function.handler` or `lambda_function.lambda_handler` | REST API Lambda TOKEN authorizer for Cellar routes |
| `python-cask` | Python | [`python-cask.py`](../project-assets/lambda-code/python-cask.py) | `lambda_function.lambda_handler` or console equivalent | Cellar Python test API |
| `node-barrel` | Node.js | [`node-barrel.cjs`](../project-assets/lambda-code/node-barrel.cjs) | `index.handler` or file-name equivalent | Cellar Node test API |
| `sommelier` | Python | [`sommelier.py`](../project-assets/lambda-code/sommelier.py) | `lambda_function.lambda_handler` or console equivalent | Public Table Sommelier |
| `auth-callback` | Python | [`auth-callback.py`](../project-assets/lambda-code/auth-callback.py) | `lambda_function.lambda_handler` or console equivalent | Cognito code exchange and session creation |
| `cognito-logout` | Python | [`cognito-logout.py`](../project-assets/lambda-code/cognito-logout.py) | `lambda_function.lambda_handler` or console equivalent | Session deletion and logout redirect |
| `python-sipper` | Python | [`python-sipper.py`](../project-assets/lambda-code/python-sipper.py) | `lambda_function.lambda_handler` or console equivalent | Authenticated Python user route |
| `node-sipper` | Node.js 20.x | [`node-sipper.cjs`](../project-assets/lambda-code/node-sipper.cjs) | `index.handler` or file-name equivalent | Authenticated Node user route |

> [!IMPORTANT]
> If you paste code into the Lambda console, make sure the handler setting matches the file name shown in the console. For example, `index.handler` requires an `index.py`, `index.js`, or `index.cjs` style file depending on runtime.
> If you upload Python files as ZIP packages, use a valid Python module filename such as `lambda_function.py` or `index.py`. The repository filenames preserve project naming, but hyphenated names are not valid Python module names for Lambda handlers.
> The Auth0 authorizer exposes both `handler` and `lambda_handler`, so either handler suffix works after the code is placed in a valid Python module file.

### 4.1 Upload Lambda Code

For the plain Python and Node route handlers, the fastest console workflow is to paste the source into the Lambda code editor.

1. Open the Lambda function.
2. Go to **Code**.
3. Paste the matching source file from [`project-assets/lambda-code/`](../project-assets/lambda-code/).
4. Confirm the runtime and handler match the file in the console.
5. Click **Deploy** if prompted.

For `auth0-jwt-authorizer`, upload a ZIP package instead of pasting only the `.py` file. The function imports `jwt`, and Lambda does not include PyJWT by default.

Build the package locally:

```bash
cd REST/project-assets/lambda-code

mkdir -p auth0-authorizer-build
cp auth0-jwt-authorizer.py auth0-authorizer-build/lambda_function.py
python3 -m pip install -r requirements-auth0-jwt-authorizer.txt -t auth0-authorizer-build

cd auth0-authorizer-build
zip -r ../auth0-jwt-authorizer.zip .
```

`auth0-authorizer-build/` is a temporary local packaging directory. It does not need to be committed when `auth0-jwt-authorizer.zip` is already present. Rebuild the ZIP when dependency versions, runtime versions, or the authorizer source changes.

Upload it in the Lambda console:

1. Open `auth0-jwt-authorizer`.
2. Go to **Code**.
3. Choose **Upload from**.
4. Select **.zip file**.
5. Upload `auth0-jwt-authorizer.zip`.
6. Set the handler to `lambda_function.handler` or `lambda_function.lambda_handler`.
7. Click **Deploy** if prompted.

> [!WARNING]
> If the authorizer returns `No module named 'jwt'`, the Lambda code was pasted without PyJWT or the package/layer was not attached. Rebuild and upload the ZIP package or attach a compatible Lambda layer.
> If the authorizer returns a `cryptography` native library error, rebuild the package in an Amazon Linux-compatible environment or use a compatible Lambda layer.

### Lambda Handler Map

| Function | Implementation rationale |
| --- | --- |
| `auth0-jwt-authorizer` | Validates Auth0 RS256 JWTs for API Gateway REST API because REST APIs do not use HTTP API JWT authorizers |
| `python-cask` | Minimal internal Python Cellar route used to verify Auth0-protected API Gateway access |
| `node-barrel` | Minimal internal Node Cellar route used to verify the same Auth0 protection across runtimes |
| `sommelier` | Public Table landing page that builds Cognito Hosted UI links and stores `oauth_state` in an HttpOnly cookie |
| `auth-callback` | Server-side OAuth callback that validates `state`, exchanges `code`, extracts user claims, creates a DynamoDB session, and redirects to Chalice |
| `cognito-logout` | Deletes the local DynamoDB session, clears the local cookie, and redirects through Cognito logout |
| `python-sipper` | Reads `sessionId` from the REST API `Cookie` header and validates against DynamoDB |
| `node-sipper` | Mirrors Python sipper logic with AWS SDK v3 DynamoDB client |

> [!NOTE]
> REST API Lambda proxy events send browser cookies in `headers.Cookie`. The sipper and logout code keep HTTP API `event.cookies` support only as a compatibility fallback for local testing or future comparison builds.

> [!IMPORTANT]
> `auth0-jwt-authorizer.py` uses `PyJWT` with cryptography support. Package that Lambda with [`requirements-auth0-jwt-authorizer.txt`](../project-assets/lambda-code/requirements-auth0-jwt-authorizer.txt) or attach a Lambda layer that provides `PyJWT[crypto]` before using the REST API authorizer in AWS.


## 5. Configure Lambda Environment Variables

Set these values after each Lambda is created. Keep secrets out of source files. Console configuration or a managed secret store should own deployment-specific values.

> [!IMPORTANT]
> Use the same `<API_ID>`, `<AWS_REGION>`, and `prod` stage consistently across Cognito URLs, Lambda environment variables, and API Gateway route tests.

> [!IMPORTANT]
> Keep these values handy before filling Lambda environment variables:

| Parameter | Console Location | Value |
| --- | --- | --- |
| API ID | API Gateway REST API details | `<API_ID>` |
| API base URL | API Gateway stage details | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod` |
| API host | Derived from API invoke URL | `<API_ID>.execute-api.<AWS_REGION>.amazonaws.com` |
| Cognito client ID | Cognito app client details | `<COGNITO_APP_CLIENT_ID>` |
| Cognito client secret | Cognito app client details, show client secret | `<COGNITO_CLIENT_SECRET>` |
| Cognito Hosted UI domain | Cognito domain settings | `<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com` |
| Session table | DynamoDB table details | `tawny-port-sessions` |
| Auth0 issuer | Auth0 application or tenant settings | `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/` |
| Auth0 audience | Auth0 API identifier | `<AUTH0_AUDIENCE>` |

### `sommelier`

| Key | Value |
| --- | --- |
| `CALLBACK_REDIRECT_URI` | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/auth/callback` |
| `CLIENT_ID` | `<COGNITO_APP_CLIENT_ID>` |
| `COGNITO_DOMAIN` | `<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com` |

### `auth-callback`

| Key | Value |
| --- | --- |
| `BASE_URL` | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/chalice` |
| `CLIENT_ID` | `<COGNITO_APP_CLIENT_ID>` |
| `CLIENT_SECRET` | `<COGNITO_CLIENT_SECRET>` |
| `COGNITO_DOMAIN` | `<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com` |
| `REDIRECT_URI` | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/auth/callback` |
| `SESSION_TABLE` | `tawny-port-sessions` |
| `COOKIE_DOMAIN` | `<API_ID>.execute-api.<AWS_REGION>.amazonaws.com` |
| `SOMMELIER_URL` | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier` |

### `cognito-logout`

| Key | Value |
| --- | --- |
| `CLIENT_ID` | `<COGNITO_APP_CLIENT_ID>` |
| `COGNITO_DOMAIN` | `<COGNITO_DOMAIN_PREFIX>.auth.<AWS_REGION>.amazoncognito.com` |
| `COOKIE_DOMAIN` | `<API_ID>.execute-api.<AWS_REGION>.amazonaws.com` |
| `POST_LOGOUT_REDIRECT_URI` | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier` |
| `SESSION_TABLE` | `tawny-port-sessions` |

### `python-sipper`

| Key | Value |
| --- | --- |
| `SESSION_TABLE` | `tawny-port-sessions` |

### `node-sipper`

| Key | Value |
| --- | --- |
| `SESSION_TABLE` | `tawny-port-sessions` |

### `python-cask` and `node-barrel`

No environment variables are required.

### `auth0-jwt-authorizer`

| Key | Value |
| --- | --- |
| `AUTH0_ISSUER` | `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/` |
| `AUTH0_AUDIENCE` | `<AUTH0_AUDIENCE>` |
| `AUTH0_JWKS_URI` | `https://<AUTH0_TENANT>.<AUTH0_REGION>.auth0.com/.well-known/jwks.json` |

> [!CAUTION]
> `CLIENT_SECRET` belongs only on `auth-callback`. Do not configure it on `sommelier`, sipper functions, frontend code, or public documentation.

## 6. Configure IAM Roles

Every Lambda execution role needs CloudWatch Logs permissions. Only session-aware Lambdas need DynamoDB access.

> [!TIP]
> Start with one execution role per Lambda. It makes least-privilege permissions easier to audit because each function only receives the DynamoDB actions it actually uses.

> [!IMPORTANT]
> Keep these values handy for CloudWatch Logs ARNs, DynamoDB policy resources, API Gateway authorizer permissions, and Lambda execution role review:

| Parameter | Console Location | Value |
| --- | --- | --- |
| AWS account ID | AWS account menu or IAM ARN details | `<AWS_ACCOUNT_ID>` |
| AWS region | AWS Console region selector | `<AWS_REGION>` |
| Session table ARN | DynamoDB table details | `arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions` |
| Lambda log group pattern | CloudWatch Logs | `/aws/lambda/<FUNCTION_NAME>` |
| Authorizer Lambda name | Lambda function details | `auth0-jwt-authorizer` |

### 6.1 CloudWatch Logs

Use this ARN pattern in Lambda logging policies:

```text
arn:aws:logs:<AWS_REGION>:<AWS_ACCOUNT_ID>:log-group:/aws/lambda/<FUNCTION_NAME>:*
```

### 6.2 DynamoDB Session Table ARN

Use this table ARN pattern:

```text
arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions
```

### 6.3 DynamoDB Actions By Function

| Lambda function | DynamoDB permissions |
| --- | --- |
| `auth0-jwt-authorizer` | None |
| `auth-callback` | `dynamodb:PutItem` |
| `python-sipper` | `dynamodb:GetItem` |
| `node-sipper` | `dynamodb:GetItem` |
| `cognito-logout` | `dynamodb:GetItem`, `dynamodb:DeleteItem` |
| `sommelier` | None |
| `python-cask` | None |
| `node-barrel` | None |

Example policy for `auth-callback`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions"
    }
  ]
}
```

Example policy for sipper functions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem"],
      "Resource": "arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions"
    }
  ]
}
```

Example policy for `cognito-logout`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:<AWS_REGION>:<AWS_ACCOUNT_ID>:table/tawny-port-sessions"
    }
  ]
}
```

Use one execution role per Lambda function and keep DynamoDB permissions limited to the functions that participate in the browser session flow.

| Category | Guidance |
| --- | --- |
| Role pattern | One Lambda role per function |
| Cellar test routes | No DynamoDB permissions required |
| Session-aware routes | Least-privilege DynamoDB access only |
| Deployment-specific values | AWS account ID, AWS region, and generated role suffixes if roles are created by the console |

---

# API Gateway Configuration

## 7. Configure API Gateway

Use API Gateway REST API for this deployment. Each route is built as a resource plus an explicit method, and every Lambda integration should use Lambda proxy integration so the functions receive the REST API event shape directly.

> [!IMPORTANT]
> This REST build is intentionally separate from the earlier HTTP API build. Do not mix REST and HTTP API invoke URLs inside Cognito callback URLs, Lambda environment variables, cookie domains, or logout URLs.

### 7.1 Create The REST API

Create the API Gateway container before adding resources, methods, integrations, or authorizers.

1. Open **AWS Console**.
2. Go to **API Gateway**.
3. Choose **Create API**.
4. Under **REST API**, choose **Build**.
5. Choose **New API**.
6. Configure:

| Field | Value |
| --- | --- |
| API name | `tawny-port-rest` |
| Description | `Tawny Port REST API implementation` |
| Endpoint type | Regional |

7. Choose **Create API**.

After creation, record the generated values:

> [!IMPORTANT]
> Keep these values handy for Cognito redirect URLs, Lambda environment variables, cookie domains, authorizer configuration, and route tests:

| Parameter | Console Location | Value |
| --- | --- | --- |
| API name | API Gateway REST API details | `tawny-port-rest` |
| REST API ID | API Gateway REST API details | `<API_ID>` |
| Root resource ID | API Gateway resources tree | Generated by API Gateway |
| Stage | API Gateway stage details | `prod` |
| Invoke URL after deployment | API Gateway stage details | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod` |
| API host | Derived from invoke URL | `<API_ID>.execute-api.<AWS_REGION>.amazonaws.com` |

Use those values later in Cognito callback URLs, Lambda environment variables, cookie domains, authorizer configuration, and route tests.

> [!IMPORTANT]
> The API name is stable: `tawny-port-rest`. The generated REST API ID and invoke URL are deployment-specific and must be replaced for each new build.

### 7.2 Stage

| Field | Value |
| --- | --- |
| Stage | `prod` |
| Invoke URL pattern | `https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod` |

> [!IMPORTANT]
> In REST API, the `prod` stage is created when you deploy the API. Resource paths do not include `/prod`. The stage appears in the invoke URL only.

### 7.3 Routes And Integrations

Create these resources and methods under the REST API resource tree. For each method, choose **Lambda Function** integration and enable **Use Lambda Proxy integration**.

| Resource path | Method | Lambda integration | Authorization |
| --- | --- | --- | --- |
| `/cellar/python-cask` | GET | `python-cask` | `tawny-port-auth0-jwt` |
| `/cellar/node-barrel` | GET | `node-barrel` | `tawny-port-auth0-jwt` |
| `/table/sommelier` | GET | `sommelier` | None |
| `/table/auth/callback` | GET | `auth-callback` | None |
| `/table/auth/logout` | GET | `cognito-logout` | None |
| `/chalice/python-sipper` | GET | `python-sipper` | None at API Gateway; Lambda validates session |
| `/chalice/node-sipper` | GET | `node-sipper` | None at API Gateway; Lambda validates session |

> [!WARNING]
> If a route returns a JSON wrapper like `{"statusCode":200,"headers":...,"body":"<html>..."}`, Lambda proxy integration is not enabled for that method. Enable proxy integration, save the method, and redeploy the `prod` stage.

### 7.3.1 Method Guidance

Use `GET` for the current routes:

- Sommelier landing page
- OAuth callback
- logout redirect
- sipper pages
- simple Cellar test endpoints

Avoid `ANY` until the route truly needs multiple methods. Keeping methods explicit makes REST API authorization and troubleshooting clearer.

### 7.3.2 Auth0 Lambda Authorizer Rules

For Cellar routes, the REST API Lambda TOKEN authorizer validates issuer and audience inside `auth0-jwt-authorizer`.

| REST API authorizer field | Value |
| --- | --- |
| Authorizer name | `tawny-port-auth0-jwt` |
| Type | Lambda |
| Lambda function | `auth0-jwt-authorizer` |
| Lambda event payload | Token |
| Token source | `Authorization` |
| Token validation | `^Bearer [-0-9a-zA-Z._]*$` |
| Authorization caching | `0` during testing, `300` after validation |
| Lambda invoke role | Leave blank unless your org requires API Gateway to assume a dedicated role |

> [!IMPORTANT]
> Keep these values handy for REST API Cellar route authorization:

| Parameter | Console Location | Value |
| --- | --- | --- |
| Authorizer name | API Gateway authorizer details | `tawny-port-auth0-jwt` |
| Lambda function | API Gateway authorizer details | `auth0-jwt-authorizer` |
| Lambda event payload | API Gateway authorizer details | Token |
| Token source | API Gateway authorizer details | `Authorization` |
| Token validation | API Gateway authorizer details | `^Bearer [-0-9a-zA-Z._]*$` |
| Authorization caching | API Gateway authorizer details | `0` during testing, `300` after validation |
| Lambda invoke role | API Gateway authorizer details | Leave blank unless required by your org |

> [!WARNING]
> In the REST API console, the token source field automatically prepends `method.request.header.`. Enter only `Authorization`.

Most authorizer failures in this project come from issuer, audience, token parsing, packaging dependencies, or route binding mistakes. If `/cellar/*` fails, inspect the JWT `iss` and `aud` claims before changing Cellar Lambda code.

Attach `tawny-port-auth0-jwt` only to:

- `GET /cellar/python-cask`
- `GET /cellar/node-barrel`

Leave Table and Chalice methods with authorization set to `None`.


### 7.4 Lambda Invoke Permission Format

API Gateway usually adds invoke permissions automatically when integrations are created in the console. If you need to verify manually, use this source ARN pattern:

```text
arn:aws:execute-api:<AWS_REGION>:<AWS_ACCOUNT_ID>:<API_ID>/prod/GET/<ROUTE_PATH>
```

Correct callback source ARN shape:

```text
arn:aws:execute-api:<AWS_REGION>:<AWS_ACCOUNT_ID>:<API_ID>/prod/GET/table/auth/callback
```

Incorrect shape:

```text
arn:aws:execute-api:<AWS_REGION>:<AWS_ACCOUNT_ID>:<API_ID>/prod/GET/prod/table/auth/callback
```

## 8. Confirm Lambda Triggers

Each Lambda should show API Gateway as its trigger after the routes and integrations are created.

| Lambda function | Trigger |
| --- | --- |
| `auth0-jwt-authorizer` | API Gateway REST API authorizer invocation for `/cellar/*` |
| `python-cask` | `GET /cellar/python-cask` |
| `node-barrel` | `GET /cellar/node-barrel` |
| `sommelier` | `GET /table/sommelier` |
| `auth-callback` | `GET /table/auth/callback` |
| `cognito-logout` | `GET /table/auth/logout` |
| `python-sipper` | `GET /chalice/python-sipper` |
| `node-sipper` | `GET /chalice/node-sipper` |

No Cognito User Pool Lambda triggers are required for this build.

> [!NOTE]
> In this project, “Lambda trigger” means API Gateway invokes the Lambda integration. Cognito User Pool triggers such as pre sign-up, post confirmation, and pre token generation are not part of the current implementation.

---

# Testing

## 9. Test The Deployment

Test the browser path first, then the protected internal path. That order verifies the session system before moving into Auth0 authorizer troubleshooting.

> [!TIP]
> Use a private browser window for negative session tests. It avoids a valid `sessionId` cookie from a previous successful login masking session-validation problems.

### 9.1 Test Table Sommelier

Open:

```text
https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier
```

Expected result:

- The Sommelier page loads.
- Python and Node login options route to Cognito Hosted UI.
- The Cognito login URL uses `/prod/table/auth/callback` as the callback target.

### 9.2 Test Cognito Login And Callback

1. Select a sipper option from the Table Sommelier.
2. Sign in through Cognito Hosted UI.
3. Confirm Cognito redirects to:

```text
/prod/table/auth/callback?code=<AUTHORIZATION_CODE>&state=<TARGET>
```

4. Confirm the callback redirects to one of:

```text
/prod/chalice/python-sipper
/prod/chalice/node-sipper
```

Expected result:

- A `sessionId` cookie is set.
- A matching item appears in `tawny-port-sessions`.
- The selected sipper route returns an authenticated response.

### 9.3 Test Sipper Routes Without A Session

Open a private browser window and request:

```text
https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/chalice/python-sipper
```

Expected result:

- The route rejects the request because no valid `sessionId` cookie exists.

Repeat for:

```text
https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/chalice/node-sipper
```

### 9.4 Test Logout

Open:

```text
https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/auth/logout
```

Expected result:

- DynamoDB session item is deleted.
- Browser cookie is cleared.
- User returns to `/prod/table/sommelier`.

Cognito logout endpoint documentation:


### 9.5 Test Cellar Auth0 Routes

Use the `AUTH0_TOKEN` exported in [Auth0 Token Validation](#auth0-token-validation). This smoke test confirms the deployed Cellar routes still reject anonymous traffic and accept a valid M2M bearer token.

Call Cellar without an Auth0 token:

```bash
curl -i "https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/python-cask"
```

Expected result:

- API Gateway returns `401` or `403`.

Call Cellar with a valid Auth0 M2M token:

```bash
curl -i -H "Authorization: Bearer $AUTH0_TOKEN" \
"https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/python-cask"
```

Repeat for the Node Cellar route:

```bash
curl -i -H "Authorization: Bearer $AUTH0_TOKEN" \
"https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/node-barrel"
```

Expected result:

- API Gateway authorizer accepts the token.
- The Cellar Lambda returns a successful response.
- CloudWatch logs confirm the Cellar function was invoked.

---

# Operations

## 10. Troubleshooting

Most failures land in one of four places: mismatched callback URLs, missing Lambda environment variables, DynamoDB permissions, or Auth0 issuer/audience mistakes.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Cognito redirect URI mismatch | Callback URL differs between Cognito and Lambda env vars | Make `REDIRECT_URI` and Cognito allowed callback URL identical |
| `invalid_client_secret` | Wrong app client secret or missing Basic Auth during token exchange | Confirm `CLIENT_ID` and `CLIENT_SECRET` on `auth-callback` |
| Sommelier opens Cognito but callback fails | Callback Lambda missing env vars or IAM permissions | Check `auth-callback` env vars and DynamoDB `PutItem` permission |
| Login succeeds but sipper rejects user | Missing cookie, wrong cookie domain, or no DynamoDB session item | Verify `sessionId` cookie and `tawny-port-sessions` item |
| Logout returns to Sommelier but session remains | Logout role cannot delete DynamoDB item | Add `dynamodb:DeleteItem` to `cognito-logout` role |
| Cellar route returns `401` | Missing or invalid Auth0 bearer token | Check Auth0 issuer, audience, and token header |
| Cellar route accepts no token | Auth0 authorizer not attached | Attach `tawny-port-auth0-jwt` to `/cellar` routes only |
| `invalid_token` or base64 decode error | Full JSON token response was stored instead of raw JWT | Recreate `AUTH0_TOKEN` with `jq -r '.access_token'` |
| Cognito sends `?code=` to a protected route | Cognito callback was pointed at Chalice instead of Table | Use `/prod/table/auth/callback` as the app client callback URL |
| Node Lambda import error | Handler mismatch or SDK/runtime issue | Use Node.js 20.x and confirm handler file name matches Runtime settings |
| No CloudWatch logs | Missing logging permissions | Add CloudWatch Logs permissions to Lambda role |



## Final Verification Checklist

- [ ] `tawny-port-sessions` DynamoDB table exists with `sessionId` partition key.
- [ ] TTL is enabled on `expiresAt`.
- [ ] API Gateway REST API is named `tawny-port-rest`.
- [ ] API Gateway REST API has been deployed to the `prod` stage.
- [ ] `tawny-port-sippers` user pool exists.
- [ ] `port-connoisseur` app client uses Authorization code grant.
- [ ] Cognito callback URL points to `/prod/table/auth/callback`.
- [ ] Cognito sign-out URL points to `/prod/table/sommelier`.
- [ ] `CLIENT_SECRET` is configured only on `auth-callback`.
- [ ] Lambda functions are created from `project-assets/lambda-code/`.
- [ ] `auth0-jwt-authorizer` is packaged with `PyJWT[crypto]` or a compatible Lambda layer.
- [ ] API Gateway routes match the route table in this runbook.
- [ ] Auth0 Lambda TOKEN authorizer is attached only to Cellar routes.
- [ ] Auth0 M2M token is acquired and exported as `AUTH0_TOKEN`.
- [ ] Cellar routes reject missing tokens and accept `Authorization: Bearer $AUTH0_TOKEN`.
- [ ] Table routes are public.
- [ ] Chalice routes rely on Lambda session validation.
- [ ] Browser login creates a DynamoDB session.
- [ ] Sipper routes accept a valid session and reject missing sessions.
- [ ] Logout deletes the DynamoDB session and clears the cookie.

---

# References

## References

| Topic | References |
| --- | --- |
| REST API routing and Lambda proxy behavior | [API Gateway REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html), [REST API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html), [Invoking Lambda with API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html) |
| REST API Lambda authorizers and Auth0 validation | [Lambda authorizers for REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html), [Configure Lambda authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/configure-api-gateway-lambda-authorization.html), [Auth0 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow), [Auth0 APIs](https://auth0.com/docs/get-started/apis) |
| Cognito managed login, OAuth exchange, and logout | [Cognito User Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html), [Managed login and hosted UI](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-hosted-ui-user-experience.html), [Managed login endpoints](https://docs.aws.amazon.com/cognito/latest/developerguide/managed-login-endpoints.html), [Authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html), [Token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html), [Logout endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html) |
| Cognito branding for the browser sign-in flow | [Managed login branding](https://docs.aws.amazon.com/cognito/latest/developerguide/managed-login-branding.html) |
| Lambda runtime configuration and roles | [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html), [Lambda execution roles](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html), [Lambda environment variables](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html) |
| DynamoDB session persistence | [Working with DynamoDB items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html), [DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html) |
| Validation and response parsing | [CloudWatch Logs for Lambda](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs.html), [jq Manual](https://jqlang.github.io/jq/manual/) |

## CLI Command References

### General CLI References

| Command | Reference |
| --- | --- |
| `python3 -m pip` | [pip user guide](https://pip.pypa.io/en/stable/user_guide/) |
| `python3` | [Python command line](https://docs.python.org/3/using/cmdline.html) |
| `curl` | [curl man page](https://curl.se/docs/manpage.html) |
| `jq` | [jq manual](https://jqlang.github.io/jq/manual/) |
| `zip` | [Info-ZIP manual](https://infozip.sourceforge.net/Zip.html) |

