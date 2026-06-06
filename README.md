# Tawny Port Serverless Infrastructure

Serverless AWS infrastructure demo with **API Gateway**, **Lambda**, **Cognito Hosted UI**, **Auth0 M2M auth**, and **DynamoDB-backed sessions**.

Tawny Port is built as two parallel deployments. Both demonstrate the same route-domain architecture and browser authentication model, but they differ in the API Gateway layer and Auth0 authorization strategy.

```text
From the Cellar, to the Table, through the Sommelier, into the Chalice.
```

## Deployments

Tawny Port demonstrates a practical identity split:

* Auth0 handles machine-to-machine access for internal Cellar routes.
* Cognito Hosted UI handles browser sign-in.
* Lambda performs server-side callback handling, session creation, and route logic.
* DynamoDB stores short-lived session records keyed by `sessionId`.
* HttpOnly cookies keep Cognito tokens out of browser-facing application routes.

Start with the deployment that matches your API Gateway target or authorization strategy:

* [HTTPS Deployment](HTTPS/README.md) (API Gateway built-in JWT authorizer)
* [REST Deployment](REST/README.md) (Lambda TOKEN authorizer)

Both deployment runbooks include end-to-end verification for the two identity paths:

* **Auth0 M2M:** token acquired, exported, passed as `Authorization: Bearer $AUTH0_TOKEN`, and validated against protected Cellar routes.
* **Cognito user flow:** Hosted UI login, callback handling, DynamoDB session creation, and Chalice route validation.

For a smaller companion guide that explains Cognito `USER_AUTH`, `SELECT_CHALLENGE`, `SECRET_HASH`, MFA, and JWT validation without the full Tawny Port application, see [Cognito CLI Auth Flow](../cognito-cli-auth-flow/README.md).

> [!IMPORTANT]
> Auth0 validation is required for Cellar route testing. Cognito login validates Table and Chalice, but it does not authorize `/prod/cellar/*`.

## Platform Overview

The project separates API access by route domain instead of mixing every trust model into one route family.

| Domain | Route pattern | Primary user | Authorization model |
| --- | --- | --- | --- |
| Cellar | `/prod/cellar/*` | Developer or service client | Auth0 M2M bearer token |
| Table | `/prod/table/*` | Browser user before app session | Public route plus Cognito Hosted UI redirect |
| Chalice | `/prod/chalice/*` | Browser user after login | Lambda validates `sessionId` against DynamoDB |

The browser flow starts at the Table Sommelier, redirects to Cognito Hosted UI, returns through the callback, creates a short-lived DynamoDB session, and then enters Chalice through a secure HttpOnly cookie.

## HTTPS vs REST

Both deployments preserve the same project model. The difference is how API Gateway is configured.

| Area | HTTPS Deployment | REST Deployment |
| --- | --- | --- |
| API Gateway name | `tawny-port-https` | `tawny-port-rest` |
| API Gateway type | HTTP API | REST API |
| Cellar authorization | Built-in JWT authorizer | Lambda TOKEN authorizer named `tawny-port-auth0-jwt` |
| Lambda event shape | HTTP API style events, including `event.cookies` | REST API Lambda proxy events, primarily `headers.Cookie` |
| Multiple cookies | HTTP API response cookie handling | REST `multiValueHeaders` for multiple `Set-Cookie` headers |
| Auth0 authorizer code | No custom authorizer Lambda required | Includes `auth0-jwt-authorizer.py` and requirements for packaging |
| Best fit | Lean HTTP API deployment | REST API deployment with explicit method and authorizer control |

> [!IMPORTANT]
> Keep deployment URLs separated. Do not mix HTTP API and REST API invoke URLs inside Cognito callback URLs, Lambda environment variables, cookie domains, or logout URLs.

## Repository Structure

```text
repo-root/
├── HTTPS/
│   ├── README.md
│   ├── env.example
│   ├── docs/
│   └── project-assets/lambda-code/
├── REST/
│   ├── README.md
│   ├── env.example
│   ├── docs/
│   └── project-assets/lambda-code/
└── shared/
    └── tawny-port-brand/
```

## Shared Assets

Branding assets are shared across both implementations:

[`shared/tawny-port-brand/`](shared/tawny-port-brand/)

Use the shared brand directory for Cognito Managed Login assets, favicons, logos, background images, and the brand color/type quick sheet. Each implementation links back to this shared location rather than keeping separate branding source paths.
