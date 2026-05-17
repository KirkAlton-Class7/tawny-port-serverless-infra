# Tawny Port API - HTTPS Version

HTTP API implementation of the Tawny Port serverless infrastructure demo.<br>
View the REST version [here](../REST/README.md) if you prefer that implementation.<br><br>

Tawny Port separates browser login from internal API access so each route family has the right trust boundary:

* **Cellar** routes use Auth0 machine-to-machine tokens for developer and service access.
* **Table** routes handle the public Sommelier, Cognito callback, and logout path.
* **Chalice** routes use an HttpOnly `sessionId` cookie backed by DynamoDB.

```text
From the Cellar, to the Table, through the Sommelier, into the Chalice.
```

> [!IMPORTANT]
> This folder documents the HTTP API implementation. Keep its invoke URL, Cognito callback URLs, Lambda environment variables, and cookie domain separate from the REST implementation.

## Documentation

| Document | Use |
| --- | --- |
| [Architecture](docs/architecture.md) | Request flow, route boundaries, and implementation notes |
| [Full Runbook](docs/tawny-port-https-runbook.md) | Console implementation guide from AWS setup through validation |
| [Shared Brand Identity](../shared/tawny-port-brand/brand-identity.md) | Cognito Managed Login color and type reference |
| [REST Version](../REST/README.md) | Companion REST API implementation |

## Project Assets

Console deployment source files for this implementation are kept under `HTTPS/project-assets/`.

| Path | Purpose |
| --- | --- |
| [project-assets/lambda-code](project-assets/lambda-code/) | Lambda source files for the HTTP API implementation |
| [../shared/tawny-port-brand](../shared/tawny-port-brand/) | Shared Cognito Managed Login branding assets |

## Architecture Summary

The HTTPS version uses API Gateway **HTTP API** routes with Lambda integrations and a built-in JWT authorizer for Auth0-protected Cellar routes.

| API Gateway field | Value |
| --- | --- |
| API name | `tawny-port-https` |
| API type | HTTP API |
| Stage | `prod` |

| Domain | Route pattern | Authentication model | Purpose |
| --- | --- | --- | --- |
| Cellar | `/prod/cellar/*` | API Gateway HTTP API JWT authorizer using Auth0 issuer and audience | Internal developer and machine-to-machine API access |
| Table | `/prod/table/*` | Public routes plus Cognito Hosted UI | Browser Sommelier, OAuth callback, logout |
| Chalice | `/prod/chalice/*` | Lambda validates `sessionId` cookie against DynamoDB | Authenticated user-facing sipper routes |

> [!WARNING]
> Keep Auth0 authorization scoped to Cellar. Table and Chalice depend on Cognito authorization-code flow, HttpOnly cookies, and DynamoDB session validation.

## Browser Authentication Flow

The browser flow starts at Table, leaves for Cognito, returns through the callback, and enters Chalice only after a DynamoDB session exists.

```mermaid
flowchart TD

BLOG["<b>DIAGRAM PLACEHOLDER</b>"]
```

Flow notes:

* `sommelier` builds Cognito Hosted UI login links with `response_type=code`, `redirect_uri`, `scope`, and a composite `state`.
* `oauth_state` is set as an HttpOnly CSRF cookie before the browser leaves for Cognito.
* Cognito redirects to `/prod/table/auth/callback` with `code` and `state`.
* `auth-callback` validates `state`, exchanges the authorization code, creates a DynamoDB session, and sets `sessionId`.
* Sipper Lambdas authorize by reading `sessionId` and validating it against `tawny-port-sessions`.

## HTTP API Implementation Notes

| Boundary | Standard pattern |
| --- | --- |
| Browser to API | API Gateway HTTP API route invokes Lambda integration |
| Browser to Cognito | Cognito Hosted UI authorization-code redirect flow |
| Callback to Cognito | Server-side confidential client token exchange at `/oauth2/token` |
| Browser session | HttpOnly `sessionId` cookie, not browser-exposed Cognito tokens |
| Session persistence | DynamoDB table with `sessionId` partition key and `expiresAt` TTL |
| Cellar authorization | HTTP API JWT authorizer using Auth0 issuer and audience |

Implementation details:

* Lambda handlers are written for HTTP API event behavior, including `event.cookies`.
* Cellar routes use the API Gateway JWT authorizer named `tawny-port-auth0-jwt`.
* Table and Chalice routes do not use the Auth0 authorizer.
* `CLIENT_SECRET` belongs only in `auth-callback` configuration or a managed secret store.

## Get Started

Use the [Tawny Port - HTTPS Runbook](docs/tawny-port-https-runbook.md) to get started with:

* DynamoDB session table setup
* Auth0 machine-to-machine configuration
* Cognito Hosted UI and app client setup
* Lambda creation, handlers, permissions, and environment variables
* API Gateway HTTP API named `tawny-port-https`
* API Gateway HTTP API routes, integrations, and authorizers
* Testing, troubleshooting, and official reference links
