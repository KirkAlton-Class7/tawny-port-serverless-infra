# Tawny Port Serverless Infrastructure Advanced Note

This note builds on [[class7_advanced/cognito-cli-auth-flow-class-note]].

The Cognito CLI lab isolates the identity mechanics: `USER_AUTH`, challenge negotiation, MFA, token issuance, and API Gateway token validation. Tawny Port turns those mechanics into a fuller serverless application pattern with separate trust zones, browser login, internal machine access, Lambda route handlers, and DynamoDB-backed sessions.

The project line still carries the architecture:

```text
From the Cellar, to the Table, through the Sommelier, into the Chalice.
```

That sentence is not just branding. It is the request map.

```text
Cellar  -> internal API access with Auth0 M2M
Table   -> public browser entry and Cognito callback handling
Sommelier -> route selector that sends users to Cognito Hosted UI
Chalice -> authenticated user experience after local session creation
```

## Links

- [[class7_advanced/00-class-7-advanced-main]]
- [[class7_advanced/cognito-cli-auth-flow-class-note]]
- [[class7_advanced/api-gateway-and-lambda-integration]]
- [[class7_advanced/aws-lambda-basics]]
- [[class7_advanced/class7-lab-aws-lambda]]
- [[aws/real-world-patterns-for-aws-lambda]]

## Repository References

| Source | Role |
| --- | --- |
| `/Users/kirk/Codex/sandbox/tawny-port-serverless-infra` | Main Tawny Port repository |
| `README.md` | Project quickstart and implementation split |
| `HTTPS/docs/tawny-port-https-runbook.md` | HTTP API implementation runbook |
| `REST/docs/tawny-port-rest-runbook.md` | REST API implementation runbook |
| `HTTPS/project-assets/lambda-code/` | HTTP API Lambda source |
| `REST/project-assets/lambda-code/` | REST API Lambda source and Auth0 authorizer package |
| `shared/tawny-port-brand/brand-identity.md` | Cognito managed login brand identity |
| `/Users/kirk/Codex/sandbox/cognito-cli-auth-flow` | Companion Cognito CLI identity lab |

## Resource Links

These are the official references that support the project architecture.

| Topic | Resource |
| --- | --- |
| API Gateway HTTP APIs | [AWS API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html) |
| HTTP API JWT authorizers | [Control access to HTTP APIs with JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html) |
| HTTP API Lambda proxy | [HTTP API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html) |
| API Gateway REST APIs | [AWS API Gateway REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html) |
| REST API Lambda authorizers | [Use API Gateway Lambda authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html) |
| REST API Lambda proxy | [Lambda proxy integrations for REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html) |
| Lambda with API Gateway | [Using Lambda with API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html) |
| Cognito User Pools | [Amazon Cognito user pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html) |
| Cognito Hosted UI | [Managed login and Hosted UI](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-hosted-ui-user-experience.html) |
| Cognito endpoints | [Managed login endpoints](https://docs.aws.amazon.com/cognito/latest/developerguide/managed-login-endpoints.html) |
| Cognito authorization endpoint | [Authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html) |
| Cognito token endpoint | [Token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html) |
| Cognito logout | [Logout endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html) |
| DynamoDB TTL | [DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html) |
| Auth0 M2M | [Auth0 Client Credentials Flow](https://auth0.com/docs/flows/client-credentials-flow) |
| Auth0 APIs | [Auth0 APIs](https://auth0.com/docs/get-started/apis) |
| JWT structure | [JWT introduction](https://jwt.io/introduction) |

## Concept Overview

Tawny Port is a route-domain authentication design. It does not try to make one identity provider do every job.

```text
Auth0 protects internal API routes.
Cognito handles browser sign-in.
Lambda performs route logic and server-side OAuth callback work.
DynamoDB stores short-lived application sessions.
HttpOnly cookies keep Cognito tokens out of browser-facing routes.
```

The core implementation move is the identity split:

| Identity path | User type | Route domain | Security model |
| --- | --- | --- | --- |
| Auth0 M2M | Service client or developer | `Cellar` | Bearer token validated by API Gateway |
| Cognito Hosted UI | Browser user | `Table` | Authorization-code redirect into callback Lambda |
| Local session | Signed-in browser user | `Chalice` | `sessionId` cookie validated by Lambda against DynamoDB |

> [!important]
> The Cognito Hosted UI login does not directly authorize Cellar routes. Auth0 does not authorize Table or Chalice. Keeping those lines clean is what makes the system understandable.

## How This Builds On The CLI Auth Flow

The CLI auth-flow note teaches direct Cognito mechanics.

```text
CLI -> Cognito API -> challenge flow -> JWT tokens -> API Gateway route
```

Tawny Port uses a browser-oriented Cognito flow instead:

```text
Browser -> Sommelier -> Cognito Hosted UI -> callback Lambda -> DynamoDB session -> Chalice
```

The mental bridge:

| CLI lab concept | Tawny Port production pattern |
| --- | --- |
| `USER_AUTH` and challenge flow | Cognito Hosted UI owns the interactive user login |
| Raw JWT returned to CLI | Callback Lambda exchanges `code` for tokens server-side |
| Token passed to API Gateway | Opaque `sessionId` cookie is passed to Chalice |
| API Gateway validates Cognito JWT | Lambda validates local session in DynamoDB |
| Barebones protected route | Browser app route with session state |

Resource links for this section: [Cognito authentication](https://docs.aws.amazon.com/cognito/latest/developerguide/authentication.html), [authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html), and [token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html).

## Route Taxonomy

The route names carry meaning. The stage is the environment; the next path segment is the trust boundary.

```text
/<stage>/<domain>/<service>
```

Current implementation:

```text
/prod/cellar/python-cask
/prod/cellar/node-barrel

/prod/table/sommelier
/prod/table/auth/callback
/prod/table/auth/logout

/prod/chalice/python-sipper
/prod/chalice/node-sipper
```

| Domain | Route pattern | Purpose | Auth boundary |
| --- | --- | --- | --- |
| Cellar | `/prod/cellar/*` | Internal API examples | Auth0 M2M |
| Table | `/prod/table/*` | Browser entry, callback, logout | Public entry plus Cognito redirect |
| Chalice | `/prod/chalice/*` | Authenticated user-facing responses | Lambda session validation |

> [!warning]
> Do not attach the Auth0 authorizer to `/table/*` or `/chalice/*`. Cellar is the machine/API boundary. Table and Chalice are the browser-user boundary.

## Request Flow

The browser path:

```text
Browser
  -> /prod/table/sommelier
  -> Cognito Hosted UI
  -> /prod/table/auth/callback?code=...&state=...
  -> Cognito /oauth2/token
  -> DynamoDB tawny-port-sessions
  -> Set-Cookie: sessionId=...
  -> /prod/chalice/python-sipper or /prod/chalice/node-sipper
```

The Cellar path:

```text
M2M client
  -> Auth0 /oauth/token
  -> access token
  -> Authorization: Bearer <token>
  -> /prod/cellar/python-cask or /prod/cellar/node-barrel
  -> API Gateway authorizer
  -> Lambda
```

The logout path:

```text
Browser
  -> /prod/table/auth/logout
  -> Lambda reads sessionId
  -> DynamoDB DeleteItem
  -> clear cookie
  -> Cognito logout endpoint
  -> /prod/table/sommelier
```

Resource links for this section: [HTTP API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html), [REST API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html), and [Cognito logout endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html).

## Architecture Responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| Auth0 | M2M token issuance for Cellar clients | Browser user login |
| Cognito Hosted UI | Browser authentication and authorization-code redirect | Application session storage |
| API Gateway | Routing, Lambda integration, authorizer enforcement | Business logic |
| Lambda | Callback exchange, route behavior, session checks | Long-term user database |
| DynamoDB | Short-lived session records | Identity provider duties |
| Browser cookie | Opaque session pointer | Raw Cognito token storage |

The cleanest way to debug Tawny Port is to ask which component should have acted before Lambda ran.

```text
If Cellar fails before Lambda logs appear, check Auth0 and API Gateway.
If callback fails, check Cognito URL values and Lambda environment variables.
If Chalice fails after login, check cookies, DynamoDB, and Lambda IAM.
```

## HTTP API Version

The HTTPS implementation uses API Gateway HTTP API.

| Area | Pattern |
| --- | --- |
| Folder | `HTTPS/` |
| Runbook | `HTTPS/docs/tawny-port-https-runbook.md` |
| API Gateway name | `tawny-port-https` |
| API Gateway type | HTTP API |
| Cellar auth | Built-in JWT authorizer |
| Event shape | HTTP API Lambda proxy event |
| Cookie handling | `event.cookies` plus compatibility parsing |
| Auth0 authorizer Lambda | Not required |

The HTTP API version is the cleaner fit when the authorizer can be expressed as standard JWT issuer/audience validation.

Implementation checkpoint:

```text
Create API Gateway HTTP API first
  -> API name: tawny-port-https
  -> Stage: prod
  -> Record API ID, invoke URL, and API host
  -> Add routes, integrations, and JWT authorizer
```

Resource links for this section: [HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html), [HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html), and [HTTP API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html).

## REST API Version

The REST implementation uses API Gateway REST API.

| Area | Pattern |
| --- | --- |
| Folder | `REST/` |
| Runbook | `REST/docs/tawny-port-rest-runbook.md` |
| API Gateway name | `tawny-port-rest` |
| API Gateway type | REST API |
| Cellar auth | Lambda TOKEN authorizer named `tawny-port-auth0-jwt` |
| Event shape | REST API Lambda proxy event |
| Cookie handling | `headers.Cookie` and `multiValueHeaders` |
| Auth0 authorizer Lambda | `auth0-jwt-authorizer.py` packaged with PyJWT |

The REST API version is more manual. That makes it better for learning resource trees, methods, deployments, Lambda TOKEN authorizers, token source configuration, and Lambda proxy response behavior.

Implementation checkpoint:

```text
Create API Gateway REST API first
  -> API name: tawny-port-rest
  -> Endpoint type: Regional
  -> Build resources and GET methods
  -> Enable Lambda proxy integrations
  -> Deploy to prod
```

Resource links for this section: [REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html), [REST API Lambda authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html), [configure Lambda authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/configure-api-gateway-lambda-authorization.html), and [REST API Lambda proxy integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html).

## Auth0 M2M Pattern

Cellar routes use Auth0 because they model internal API access.

```text
client_id + client_secret + audience
  -> Auth0 /oauth/token
  -> access_token
  -> Authorization: Bearer $AUTH0_TOKEN
  -> /prod/cellar/*
```

The audience is the anchor. If the token audience does not match the API Gateway authorizer configuration, the request should fail.

```bash
curl --request POST \
  --url https://<AUTH0_DOMAIN>/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"<AUTH0_CLIENT_ID>",
    "client_secret":"<AUTH0_CLIENT_SECRET>",
    "audience":"<AUTH0_AUDIENCE>",
    "grant_type":"client_credentials"
}'
```

Export the raw token:

```bash
export AUTH0_TOKEN="<ACCESS_TOKEN>"
```

Test Cellar:

```bash
curl -i -H "Authorization: Bearer $AUTH0_TOKEN" \
"https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/cellar/python-cask?name=AuthTester"
```

Common failures:

| Failure | Meaning |
| --- | --- |
| Missing token | API Gateway should reject before Lambda |
| Wrong audience | Token was minted for a different API |
| Wrong issuer | Auth0 domain or trailing slash mismatch |
| Expired token | Request a fresh M2M access token |
| Bad token source | REST authorizer is not reading `Authorization` correctly |

Resource links for this section: [Auth0 Client Credentials Flow](https://auth0.com/docs/flows/client-credentials-flow), [Auth0 APIs](https://auth0.com/docs/get-started/apis), and [JWT introduction](https://jwt.io/introduction).

## Cognito Hosted UI Pattern

Table routes use Cognito because they model browser-user login.

```text
/prod/table/sommelier
  -> Cognito Hosted UI
  -> /prod/table/auth/callback
```

The callback Lambda is the confidential OAuth client. It can hold `CLIENT_SECRET`, exchange the authorization code at `/oauth2/token`, decode user claims, create the local session, and redirect to Chalice.

Important boundaries:

- `sommelier` can build the login URL, but should not hold `CLIENT_SECRET`.
- `auth-callback` owns the code exchange.
- `python-sipper` and `node-sipper` should not need Cognito client secrets.
- Chalice routes should receive only `sessionId`, not raw Cognito tokens.

Resource links for this section: [Cognito managed login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-hosted-ui-user-experience.html), [authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html), [token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html), and [managed login endpoints](https://docs.aws.amazon.com/cognito/latest/developerguide/managed-login-endpoints.html).

## DynamoDB Session Pattern

`tawny-port-sessions` is a short-lived session table, not an identity store.

| Field | Purpose |
| --- | --- |
| `sessionId` | Opaque random session key stored in an HttpOnly cookie |
| `userEmail` | User claim extracted from Cognito ID token |
| `userName` | Cognito username or email fallback |
| `expiresAt` | TTL epoch seconds |

The callback writes the item. The sipper and logout Lambdas read or delete it.

```text
auth-callback -> PutItem
python-sipper -> GetItem
node-sipper -> GetItem
cognito-logout -> DeleteItem
```

This pattern keeps Cognito tokens away from browser-facing route handlers. The browser holds a session pointer, not the identity tokens themselves.

Resource links for this section: [DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html) and [Lambda execution role permissions](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html).

## Lambda Map

| Lambda | Route domain | Responsibility |
| --- | --- | --- |
| `python-cask` | Cellar | Python Auth0-protected internal route |
| `node-barrel` | Cellar | Node Auth0-protected internal route |
| `sommelier` | Table | Public selector and Cognito Hosted UI redirect builder |
| `auth-callback` | Table | OAuth code exchange, CSRF state validation, session creation |
| `cognito-logout` | Table | Session deletion, cookie clearing, Cognito logout redirect |
| `python-sipper` | Chalice | Python session-backed user route |
| `node-sipper` | Chalice | Node session-backed user route |
| `auth0-jwt-authorizer` | REST Cellar only | Auth0 RS256 JWT verification for REST API Cellar routes |

Resource links for this section: [Using Lambda with API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html), [Lambda execution roles](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html), and [CloudWatch Logs for Lambda](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs.html).

## Environment Variables

The most common Tawny Port deployment failures are caused by mixed invoke URLs or missing environment variables.

| Lambda | Required values |
| --- | --- |
| `sommelier` | `CALLBACK_REDIRECT_URI`, `CLIENT_ID`, `COGNITO_DOMAIN` |
| `auth-callback` | `BASE_URL`, `CLIENT_ID`, `CLIENT_SECRET`, `COGNITO_DOMAIN`, `COOKIE_DOMAIN`, `REDIRECT_URI`, `SESSION_TABLE`, `SOMMELIER_URL` |
| `cognito-logout` | `CLIENT_ID`, `COGNITO_DOMAIN`, `COOKIE_DOMAIN`, `POST_LOGOUT_REDIRECT_URI`, `SESSION_TABLE` |
| `python-sipper` | `SESSION_TABLE` |
| `node-sipper` | `SESSION_TABLE` |
| `auth0-jwt-authorizer` | `AUTH0_ISSUER`, `AUTH0_AUDIENCE`, optional `AUTH0_JWKS_URI` |

Keep these values in the same API Gateway family:

```text
Callback URL
Sign-out URL
Lambda BASE_URL
COOKIE_DOMAIN
SOMMELIER_URL
Cognito app client callback URLs
```

> [!warning]
> Do not mix HTTP API and REST API invoke URLs. If Sommelier points to one API family and the callback Lambda expects the other, the browser flow will fail in ways that look like Cognito or CSRF errors.

## Validation Workflow

Validate in layers.

### 1. Cellar Auth0

```text
Get Auth0 token
  -> export AUTH0_TOKEN
  -> call /prod/cellar/python-cask
  -> call /prod/cellar/node-barrel
  -> confirm anonymous calls fail
```

### 2. Table Cognito

```text
Open /prod/table/sommelier
  -> select Python or Node
  -> Cognito Hosted UI opens
  -> callback receives code and state
```

### 3. Chalice Session

```text
Callback creates DynamoDB session
  -> browser receives HttpOnly sessionId cookie
  -> sipper route validates sessionId
  -> authenticated response returns
```

### 4. Logout

```text
/prod/table/auth/logout
  -> DeleteItem from DynamoDB
  -> clear sessionId cookie
  -> redirect through Cognito logout
  -> return to Sommelier
```

## Troubleshooting Map

| Symptom | First place to check |
| --- | --- |
| Cellar returns `401` | Auth0 token `iss`, `aud`, expiration, and route authorizer |
| Cellar Lambda has no logs | API Gateway rejected the request before invoking Lambda |
| Sommelier returns JSON wrapper instead of HTML | REST method is not using Lambda proxy integration |
| Cognito says callback URL is invalid | Real API ID and region were not substituted into the URL |
| Security check failed after login | Stale code, wrong API family URL, or `oauth_state` cookie mismatch |
| Token exchange fails | `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, or Cognito domain mismatch |
| Sipper rejects after login | Missing cookie, wrong `COOKIE_DOMAIN`, or no DynamoDB session item |
| Logout does not remove session | `cognito-logout` lacks `dynamodb:DeleteItem` |
| REST Auth0 authorizer import error | PyJWT was not packaged into the Lambda ZIP |

## Study Questions

1. Why does Cellar use Auth0 instead of Cognito?
2. Why does Chalice validate a DynamoDB session instead of receiving Cognito tokens directly?
3. Which Lambda should hold `CLIENT_SECRET`, and why?
4. What breaks if the Cognito callback URL points directly to a sipper route?
5. Why does REST API need `multiValueHeaders` for multiple cookies?
6. Why does the REST version need a Lambda TOKEN authorizer while the HTTP API version can use a built-in JWT authorizer?
7. What does DynamoDB TTL clean up, and what does it not guarantee immediately?
8. Which routes should produce Lambda logs when an unauthenticated request is made?

## Validation Tasks

- [ ] Explain the difference between Cellar, Table, and Chalice.
- [ ] Trace the browser flow from Sommelier to Cognito to callback to Chalice.
- [ ] Explain why `?code=` is not a JWT.
- [ ] Identify which Lambda owns the Cognito token exchange.
- [ ] Identify which Lambda functions need DynamoDB permissions.
- [ ] Acquire an Auth0 M2M token and test both Cellar routes.
- [ ] Confirm anonymous Cellar requests fail before Lambda invocation.
- [ ] Complete Cognito Hosted UI login and confirm a DynamoDB session item is created.
- [ ] Confirm sipper routes reject missing or expired sessions.
- [ ] Complete logout and confirm the session item is deleted.

## Strategic Takeaways

- Route names can encode trust boundaries.
- Auth0 and Cognito are not interchangeable in this project; they solve different identity problems.
- Cognito Hosted UI is safer for browser login than custom password handling.
- The authorization code must be exchanged by a confidential backend component.
- A short-lived DynamoDB session table lets the app avoid exposing Cognito tokens to route handlers.
- HTTP API is cleaner when built-in JWT authorizers are enough.
- REST API is better when learning method-level configuration, deployments, and Lambda TOKEN authorizers.
- Most serverless auth bugs are boundary bugs: wrong issuer, wrong audience, wrong redirect URI, wrong cookie domain, or wrong authorizer placement.

## Study References

- [Tawny Port root README](/Users/kirk/Codex/sandbox/tawny-port-serverless-infra/README.md)
- [Tawny Port HTTPS runbook](/Users/kirk/Codex/sandbox/tawny-port-serverless-infra/HTTPS/docs/tawny-port-https-runbook.md)
- [Tawny Port REST runbook](/Users/kirk/Codex/sandbox/tawny-port-serverless-infra/REST/docs/tawny-port-rest-runbook.md)
- [Tawny Port brand identity](/Users/kirk/Codex/sandbox/tawny-port-serverless-infra/shared/tawny-port-brand/brand-identity.md)
- [[class7_advanced/cognito-cli-auth-flow-class-note]]
- [AWS API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [AWS API Gateway REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html)
- [API Gateway JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
- [API Gateway Lambda authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [Amazon Cognito managed login](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-hosted-ui-user-experience.html)
- [Amazon Cognito authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html)
- [Amazon Cognito token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html)
- [DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [Auth0 Client Credentials Flow](https://auth0.com/docs/flows/client-credentials-flow)
