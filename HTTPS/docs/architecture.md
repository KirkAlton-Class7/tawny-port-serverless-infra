# Tawny Port Architecture

Tawny Port is a serverless AWS infrastructure demo with API Gateway, Lambda, Cognito Hosted UI, Auth0 M2M auth, and DynamoDB-backed sessions.

It is built around route families with different trust boundaries. API Gateway carries the request, Lambda owns the work, Cognito handles browser sign-in, Auth0 protects internal API access, and DynamoDB keeps the short-lived browser session state.

Use this file when you need to see how the pieces move together before changing routes, authorizers, callback URLs, or session logic.

Shows:

* Browser login and callback flow
* Local session validation through DynamoDB
* Cognito logout behavior
* Auth0 machine-to-machine access for Cellar
* Infrastructure boundaries that should stay intact as the project grows

```text
From the Cellar, to the Table, through the Sommelier, into the Chalice.
```

> [!IMPORTANT]
> Examples are sanitized. Replace deployment-specific values such as API IDs, AWS regions, Cognito domains, Auth0 tenants, account IDs, and client IDs when deploying.

---

## Route Domains

Each route domain maps to a different user type and authorization model.

| Domain | Route pattern | Authentication model | Purpose |
| --- | --- | --- | --- |
| Cellar | `/prod/cellar/*` | Auth0 JWT authorizer on API Gateway | Internal developer and machine-to-machine API access |
| Table | `/prod/table/*` | Public API Gateway routes plus Cognito Hosted UI | Browser Sommelier, OAuth callback, logout |
| Chalice | `/prod/chalice/*` | Lambda validates `sessionId` cookie against DynamoDB | Authenticated user-facing sipper routes |

> [!WARNING]
> Keep Auth0 authorization scoped to Cellar. The Table callback and Chalice routes depend on Cognito code exchange, HttpOnly cookies, and DynamoDB session validation instead.

## Browser Authentication Flow

The browser flow starts at Table, leaves for Cognito, returns through the callback, and enters Chalice only after a DynamoDB session exists.

```mermaid
flowchart TD

BLOG["<b>DIAGRAM PLACEHOLDER</b>"]
```

### Flow Notes

- `sommelier` generates Cognito login links with `response_type=code`, `redirect_uri`, `scope`, and a composite `state` value.
- `oauth_state` is an HttpOnly CSRF cookie set before the browser leaves for Cognito.
- Cognito redirects back to `/prod/table/auth/callback` with `code` and `state`.
- `auth-callback` validates `state`, exchanges the authorization code at Cognito `/oauth2/token`, creates a DynamoDB session, and sets an HttpOnly `sessionId` cookie.
- Sipper Lambdas do not receive Cognito tokens from the browser. They authorize by reading `sessionId` and validating it against `tawny-port-sessions`.

## Logout Flow

Logout clears the local session before sending the browser through Cognito logout. That keeps the application session and the Cognito hosted session from drifting apart.

```mermaid
flowchart TD

BLOG["<b>DIAGRAM PLACEHOLDER</b>"]
```

### Logout Notes

- The logout Lambda deletes the local DynamoDB session first.
- The Lambda clears the local `sessionId` cookie.
- The browser is redirected through Cognito `/logout` with `client_id`, `logout_uri`, and `state`.
- Cognito redirects back to the Table Sommelier route.

## Cellar Machine-To-Machine Flow

Cellar does not use browser cookies or Cognito redirects. A developer or service requests an Auth0 access token and presents it directly to API Gateway.

```mermaid
flowchart TD

BLOG["<b>DIAGRAM PLACEHOLDER</b>"]
```

### Cellar Notes

- Auth0 is only used for `/prod/cellar/*`.
- API Gateway validates Auth0 JWTs with the `tawny-port-auth0-jwt` authorizer.
- Table and Chalice routes do not use the Auth0 authorizer.

## Infrastructure Boundaries

Use these boundaries as the guardrails when expanding the project.

| Boundary | Standard pattern used |
| --- | --- |
| Browser to API | API Gateway HTTP API route invokes Lambda proxy integrations |
| Browser to Cognito | Cognito Hosted UI authorization-code redirect flow |
| Callback to Cognito | Server-side confidential client token exchange at `/oauth2/token` |
| Browser session | HttpOnly `sessionId` cookie, not browser-exposed Cognito tokens |
| Session persistence | DynamoDB table with `sessionId` partition key and `expiresAt` TTL |
| Cellar authorization | API Gateway HTTP API JWT authorizer using Auth0 issuer and audience |

## Implementation Notes

- The Lambda code uses API Gateway HTTP API style events, including `event.cookies` support.
- For multiple cookies in an HTTP API response, prefer the HTTP API response `cookies` array or another supported multi-cookie mechanism. A single response headers map cannot safely represent two separate `Set-Cookie` headers with the same key.
- Keep `CLIENT_SECRET` only in `auth-callback` configuration or a managed secret store.
- Keep Cognito callback and logout routes public at API Gateway. Their protections are state validation, Cognito code exchange, cookie attributes, and DynamoDB session handling.

## References

| Topic | References |
| --- | --- |
| HTTP API routing and Lambda integration behavior | [API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html), [HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html), [Invoking Lambda with API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html) |
| JWT-protected developer and machine routes | [HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html), [Auth0 Client Credentials Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow), [Auth0 APIs](https://auth0.com/docs/get-started/apis) |
| Cognito-managed browser journey | [Managed login and hosted UI](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-hosted-ui-user-experience.html), [Managed login endpoints](https://docs.aws.amazon.com/cognito/latest/developerguide/managed-login-endpoints.html), [Authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html), [Token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html), [Logout endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html) |
| Session persistence and cleanup model | [Working with DynamoDB items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html), [DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html) |
