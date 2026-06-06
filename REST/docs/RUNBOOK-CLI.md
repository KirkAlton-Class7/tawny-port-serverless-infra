# Tawny Port - REST API CLI Runbook

## Purpose

Build the Tawny Port REST API deployment with AWS CLI commands, then validate the browser user experience through Cognito Managed Login.

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
| [`RUNBOOK-CONSOLE.md`](RUNBOOK-CONSOLE.md) | Companion runbook for the same architecture. |
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

# Preparation

## 1. Prepare Environment Values

Work from the repository root:

```bash
cd "$HOME/tawny-port-serverless-infra"
```

Copy the committed template and load it:

```bash
cp REST/env.example REST/.env
source REST/.env
```

Update these initial values in `REST/.env`, then reload the file:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `AUTH0_ISSUER`
- `AUTH0_AUDIENCE`
- `AUTH0_JWKS_URI`
- `AUTH0_TOKEN`
- `COGNITO_DOMAIN_PREFIX`

```bash
source REST/.env

aws sts get-caller-identity
aws --version
zip --version
python3 --version
```

## 2. Package Lambda ZIP Files

Package each repository source file with a Lambda-safe handler filename. The REST Auth0 authorizer must include PyJWT dependencies.

```bash
rm -rf REST/build
mkdir -p REST/build/zips

for name in python-cask sommelier auth-callback cognito-logout python-sipper; do
  mkdir -p "REST/build/$name"
  cp "REST/project-assets/lambda-code/$name.py" "REST/build/$name/lambda_function.py"
  (cd "REST/build/$name" && zip -qr "../zips/$name.zip" .)
done

for name in node-barrel node-sipper; do
  mkdir -p "REST/build/$name"
  cp "REST/project-assets/lambda-code/$name.cjs" "REST/build/$name/index.cjs"
  (cd "REST/build/$name" && zip -qr "../zips/$name.zip" .)
done

mkdir -p REST/build/auth0-jwt-authorizer
cp REST/project-assets/lambda-code/auth0-jwt-authorizer.py REST/build/auth0-jwt-authorizer/lambda_function.py
python3 -m pip install -r REST/project-assets/lambda-code/requirements-auth0-jwt-authorizer.txt -t REST/build/auth0-jwt-authorizer
(cd REST/build/auth0-jwt-authorizer && zip -qr ../zips/auth0-jwt-authorizer.zip .)

ls -lh REST/build/zips
```

Expected:

```text
Eight Lambda ZIP files exist under REST/build/zips.
```

---

# Core Infrastructure

## 3. Create DynamoDB Session Table

```bash
aws dynamodb create-table \
  --table-name "$SESSION_TABLE" \
  --attribute-definitions AttributeName=sessionId,AttributeType=S \
  --key-schema AttributeName=sessionId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$AWS_REGION"

aws dynamodb wait table-exists \
  --table-name "$SESSION_TABLE" \
  --region "$AWS_REGION"

aws dynamodb update-time-to-live \
  --table-name "$SESSION_TABLE" \
  --time-to-live-specification Enabled=true,AttributeName=expiresAt \
  --region "$AWS_REGION"
```

## 4. Create Lambda IAM Roles

Create the Lambda trust policy:

```bash
cat > /tmp/tawny-port-lambda-trust.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
```

Create one role per function:

```bash
for role in \
  "$AUTH0_AUTHORIZER_ROLE" \
  "$PYTHON_CASK_ROLE" \
  "$NODE_BARREL_ROLE" \
  "$SOMMELIER_ROLE" \
  "$AUTH_CALLBACK_ROLE" \
  "$COGNITO_LOGOUT_ROLE" \
  "$PYTHON_SIPPER_ROLE" \
  "$NODE_SIPPER_ROLE"; do
  aws iam create-role \
    --role-name "$role" \
    --assume-role-policy-document file:///tmp/tawny-port-lambda-trust.json

  aws iam attach-role-policy \
    --role-name "$role" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
done
```

Add DynamoDB access only where the application session flow needs it:

```bash
cat > /tmp/tawny-port-ddb-put.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem"],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${SESSION_TABLE}"
    }
  ]
}
JSON

cat > /tmp/tawny-port-ddb-get.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem"],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${SESSION_TABLE}"
    }
  ]
}
JSON

cat > /tmp/tawny-port-ddb-delete.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${SESSION_TABLE}"
    }
  ]
}
JSON

aws iam put-role-policy --role-name "$AUTH_CALLBACK_ROLE" --policy-name tawny-port-session-put --policy-document file:///tmp/tawny-port-ddb-put.json
aws iam put-role-policy --role-name "$PYTHON_SIPPER_ROLE" --policy-name tawny-port-session-get --policy-document file:///tmp/tawny-port-ddb-get.json
aws iam put-role-policy --role-name "$NODE_SIPPER_ROLE" --policy-name tawny-port-session-get --policy-document file:///tmp/tawny-port-ddb-get.json
aws iam put-role-policy --role-name "$COGNITO_LOGOUT_ROLE" --policy-name tawny-port-session-delete --policy-document file:///tmp/tawny-port-ddb-delete.json
```

Export role ARNs:

```bash
export AUTH0_AUTHORIZER_ROLE_ARN=$(aws iam get-role --role-name "$AUTH0_AUTHORIZER_ROLE" --query 'Role.Arn' --output text)
export PYTHON_CASK_ROLE_ARN=$(aws iam get-role --role-name "$PYTHON_CASK_ROLE" --query 'Role.Arn' --output text)
export NODE_BARREL_ROLE_ARN=$(aws iam get-role --role-name "$NODE_BARREL_ROLE" --query 'Role.Arn' --output text)
export SOMMELIER_ROLE_ARN=$(aws iam get-role --role-name "$SOMMELIER_ROLE" --query 'Role.Arn' --output text)
export AUTH_CALLBACK_ROLE_ARN=$(aws iam get-role --role-name "$AUTH_CALLBACK_ROLE" --query 'Role.Arn' --output text)
export COGNITO_LOGOUT_ROLE_ARN=$(aws iam get-role --role-name "$COGNITO_LOGOUT_ROLE" --query 'Role.Arn' --output text)
export PYTHON_SIPPER_ROLE_ARN=$(aws iam get-role --role-name "$PYTHON_SIPPER_ROLE" --query 'Role.Arn' --output text)
export NODE_SIPPER_ROLE_ARN=$(aws iam get-role --role-name "$NODE_SIPPER_ROLE" --query 'Role.Arn' --output text)
```

## 5. Create Lambda Functions

Wait a few seconds after IAM role creation, then create the functions:

```bash
aws lambda create-function --function-name "$AUTH0_AUTHORIZER_FUNCTION" --runtime python3.12 --handler lambda_function.handler --role "$AUTH0_AUTHORIZER_ROLE_ARN" --zip-file fileb://REST/build/zips/auth0-jwt-authorizer.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$PYTHON_CASK_FUNCTION" --runtime python3.12 --handler lambda_function.lambda_handler --role "$PYTHON_CASK_ROLE_ARN" --zip-file fileb://REST/build/zips/python-cask.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$SOMMELIER_FUNCTION" --runtime python3.12 --handler lambda_function.lambda_handler --role "$SOMMELIER_ROLE_ARN" --zip-file fileb://REST/build/zips/sommelier.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$AUTH_CALLBACK_FUNCTION" --runtime python3.12 --handler lambda_function.lambda_handler --role "$AUTH_CALLBACK_ROLE_ARN" --zip-file fileb://REST/build/zips/auth-callback.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$COGNITO_LOGOUT_FUNCTION" --runtime python3.12 --handler lambda_function.lambda_handler --role "$COGNITO_LOGOUT_ROLE_ARN" --zip-file fileb://REST/build/zips/cognito-logout.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$PYTHON_SIPPER_FUNCTION" --runtime python3.12 --handler lambda_function.lambda_handler --role "$PYTHON_SIPPER_ROLE_ARN" --zip-file fileb://REST/build/zips/python-sipper.zip --region "$AWS_REGION"

aws lambda create-function --function-name "$NODE_BARREL_FUNCTION" --runtime nodejs20.x --handler index.handler --role "$NODE_BARREL_ROLE_ARN" --zip-file fileb://REST/build/zips/node-barrel.zip --region "$AWS_REGION"
aws lambda create-function --function-name "$NODE_SIPPER_FUNCTION" --runtime nodejs20.x --handler index.handler --role "$NODE_SIPPER_ROLE_ARN" --zip-file fileb://REST/build/zips/node-sipper.zip --region "$AWS_REGION"
```

Export Lambda ARNs:

```bash
export AUTH0_AUTHORIZER_ARN=$(aws lambda get-function --function-name "$AUTH0_AUTHORIZER_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export PYTHON_CASK_ARN=$(aws lambda get-function --function-name "$PYTHON_CASK_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export NODE_BARREL_ARN=$(aws lambda get-function --function-name "$NODE_BARREL_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export SOMMELIER_ARN=$(aws lambda get-function --function-name "$SOMMELIER_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export AUTH_CALLBACK_ARN=$(aws lambda get-function --function-name "$AUTH_CALLBACK_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export COGNITO_LOGOUT_ARN=$(aws lambda get-function --function-name "$COGNITO_LOGOUT_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export PYTHON_SIPPER_ARN=$(aws lambda get-function --function-name "$PYTHON_SIPPER_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
export NODE_SIPPER_ARN=$(aws lambda get-function --function-name "$NODE_SIPPER_FUNCTION" --query 'Configuration.FunctionArn' --output text --region "$AWS_REGION")
```

---

# Identity And Session Configuration

## 6. Create The REST API

```bash
export REST_API_ID=$(aws apigateway create-rest-api \
  --name "$API_NAME" \
  --description "Tawny Port REST API deployment" \
  --endpoint-configuration types=REGIONAL \
  --query 'id' \
  --output text \
  --region "$AWS_REGION")

export ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id "$REST_API_ID" \
  --query "items[?path=='/'].id | [0]" \
  --output text \
  --region "$AWS_REGION")

export API_ENDPOINT="https://${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${API_STAGE}"
export API_HOST="${REST_API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
export CALLBACK_REDIRECT_URI="${API_ENDPOINT}/table/auth/callback"
export POST_LOGOUT_REDIRECT_URI="${API_ENDPOINT}/table/sommelier"
export BASE_CHALICE_URL="${API_ENDPOINT}/chalice"

printf '\nexport REST_API_ID=\"%s\"\nexport ROOT_RESOURCE_ID=\"%s\"\nexport API_ENDPOINT=\"%s\"\nexport API_HOST=\"%s\"\nexport CALLBACK_REDIRECT_URI=\"%s\"\nexport POST_LOGOUT_REDIRECT_URI=\"%s\"\nexport BASE_CHALICE_URL=\"%s\"\n' \
  "$REST_API_ID" "$ROOT_RESOURCE_ID" "$API_ENDPOINT" "$API_HOST" "$CALLBACK_REDIRECT_URI" "$POST_LOGOUT_REDIRECT_URI" "$BASE_CHALICE_URL" >> REST/.env

source REST/.env
```

## 7. Create Cognito User Pool, App Client, And Domain

```bash
export COGNITO_USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "$USER_POOL_NAME" \
  --query 'UserPool.Id' \
  --output text \
  --region "$AWS_REGION")

export COGNITO_APP_CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id "$COGNITO_USER_POOL_ID" \
  --client-name "$COGNITO_APP_CLIENT_NAME" \
  --generate-secret \
  --allowed-o-auth-flows-user-pool-client \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email phone \
  --supported-identity-providers COGNITO \
  --callback-urls "$CALLBACK_REDIRECT_URI" \
  --logout-urls "$POST_LOGOUT_REDIRECT_URI" \
  --query 'UserPoolClient.ClientId' \
  --output text \
  --region "$AWS_REGION")

export COGNITO_CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id "$COGNITO_USER_POOL_ID" \
  --client-id "$COGNITO_APP_CLIENT_ID" \
  --query 'UserPoolClient.ClientSecret' \
  --output text \
  --region "$AWS_REGION")

aws cognito-idp create-user-pool-domain \
  --user-pool-id "$COGNITO_USER_POOL_ID" \
  --domain "$COGNITO_DOMAIN_PREFIX" \
  --region "$AWS_REGION"

printf '\nexport COGNITO_USER_POOL_ID=\"%s\"\nexport COGNITO_APP_CLIENT_ID=\"%s\"\nexport COGNITO_CLIENT_SECRET=\"%s\"\nexport COGNITO_DOMAIN=\"%s\"\n' \
  "$COGNITO_USER_POOL_ID" "$COGNITO_APP_CLIENT_ID" "$COGNITO_CLIENT_SECRET" "$COGNITO_DOMAIN" >> REST/.env

source REST/.env
```

Use the shared brand assets in `shared/tawny-port-brand/` to style Cognito Managed Login in the AWS Console.

## 8. Configure Lambda Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name "$AUTH0_AUTHORIZER_FUNCTION" \
  --environment "Variables={AUTH0_ISSUER=$AUTH0_ISSUER,AUTH0_AUDIENCE=$AUTH0_AUDIENCE,AUTH0_JWKS_URI=$AUTH0_JWKS_URI}" \
  --region "$AWS_REGION"

aws lambda update-function-configuration \
  --function-name "$SOMMELIER_FUNCTION" \
  --environment "Variables={CLIENT_ID=$COGNITO_APP_CLIENT_ID,COGNITO_DOMAIN=$COGNITO_DOMAIN,CALLBACK_REDIRECT_URI=$CALLBACK_REDIRECT_URI}" \
  --region "$AWS_REGION"

aws lambda update-function-configuration \
  --function-name "$AUTH_CALLBACK_FUNCTION" \
  --environment "Variables={BASE_URL=$BASE_CHALICE_URL,CLIENT_ID=$COGNITO_APP_CLIENT_ID,CLIENT_SECRET=$COGNITO_CLIENT_SECRET,COGNITO_DOMAIN=$COGNITO_DOMAIN,REDIRECT_URI=$CALLBACK_REDIRECT_URI,SESSION_TABLE=$SESSION_TABLE,COOKIE_DOMAIN=$API_HOST,SOMMELIER_URL=$POST_LOGOUT_REDIRECT_URI}" \
  --region "$AWS_REGION"

aws lambda update-function-configuration \
  --function-name "$COGNITO_LOGOUT_FUNCTION" \
  --environment "Variables={CLIENT_ID=$COGNITO_APP_CLIENT_ID,COGNITO_DOMAIN=$COGNITO_DOMAIN,COOKIE_DOMAIN=$API_HOST,POST_LOGOUT_REDIRECT_URI=$POST_LOGOUT_REDIRECT_URI,SESSION_TABLE=$SESSION_TABLE}" \
  --region "$AWS_REGION"

aws lambda update-function-configuration \
  --function-name "$PYTHON_SIPPER_FUNCTION" \
  --environment "Variables={SESSION_TABLE=$SESSION_TABLE}" \
  --region "$AWS_REGION"

aws lambda update-function-configuration \
  --function-name "$NODE_SIPPER_FUNCTION" \
  --environment "Variables={SESSION_TABLE=$SESSION_TABLE}" \
  --region "$AWS_REGION"
```

---

# API Gateway Routing And Authorization

## 9. Configure REST Resources, Methods, Integrations, And Authorizer

Create the resource tree:

```bash
export CELLAR_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$ROOT_RESOURCE_ID" --path-part cellar --query 'id' --output text --region "$AWS_REGION")
export TABLE_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$ROOT_RESOURCE_ID" --path-part table --query 'id' --output text --region "$AWS_REGION")
export CHALICE_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$ROOT_RESOURCE_ID" --path-part chalice --query 'id' --output text --region "$AWS_REGION")

export CELLAR_PYTHON_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$CELLAR_RESOURCE_ID" --path-part python-cask --query 'id' --output text --region "$AWS_REGION")
export CELLAR_NODE_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$CELLAR_RESOURCE_ID" --path-part node-barrel --query 'id' --output text --region "$AWS_REGION")
export TABLE_SOMMELIER_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$TABLE_RESOURCE_ID" --path-part sommelier --query 'id' --output text --region "$AWS_REGION")
export TABLE_AUTH_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$TABLE_RESOURCE_ID" --path-part auth --query 'id' --output text --region "$AWS_REGION")
export TABLE_CALLBACK_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$TABLE_AUTH_RESOURCE_ID" --path-part callback --query 'id' --output text --region "$AWS_REGION")
export TABLE_LOGOUT_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$TABLE_AUTH_RESOURCE_ID" --path-part logout --query 'id' --output text --region "$AWS_REGION")
export CHALICE_PYTHON_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$CHALICE_RESOURCE_ID" --path-part python-sipper --query 'id' --output text --region "$AWS_REGION")
export CHALICE_NODE_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$CHALICE_RESOURCE_ID" --path-part node-sipper --query 'id' --output text --region "$AWS_REGION")
```

Create methods and proxy integrations:

```bash
create_get_proxy_method () {
  local resource_id="$1"
  local lambda_arn="$2"

  aws apigateway put-method \
    --rest-api-id "$REST_API_ID" \
    --resource-id "$resource_id" \
    --http-method GET \
    --authorization-type NONE \
    --region "$AWS_REGION"

  aws apigateway put-integration \
    --rest-api-id "$REST_API_ID" \
    --resource-id "$resource_id" \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${lambda_arn}/invocations" \
    --region "$AWS_REGION"
}

create_get_proxy_method "$CELLAR_PYTHON_RESOURCE_ID" "$PYTHON_CASK_ARN"
create_get_proxy_method "$CELLAR_NODE_RESOURCE_ID" "$NODE_BARREL_ARN"
create_get_proxy_method "$TABLE_SOMMELIER_RESOURCE_ID" "$SOMMELIER_ARN"
create_get_proxy_method "$TABLE_CALLBACK_RESOURCE_ID" "$AUTH_CALLBACK_ARN"
create_get_proxy_method "$TABLE_LOGOUT_RESOURCE_ID" "$COGNITO_LOGOUT_ARN"
create_get_proxy_method "$CHALICE_PYTHON_RESOURCE_ID" "$PYTHON_SIPPER_ARN"
create_get_proxy_method "$CHALICE_NODE_RESOURCE_ID" "$NODE_SIPPER_ARN"
```

Create the Auth0 Lambda TOKEN authorizer and attach it only to Cellar methods:

```bash
export AUTH0_AUTHORIZER_ID=$(aws apigateway create-authorizer \
  --rest-api-id "$REST_API_ID" \
  --name tawny-port-auth0-jwt \
  --type TOKEN \
  --authorizer-uri "arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${AUTH0_AUTHORIZER_ARN}/invocations" \
  --identity-source method.request.header.Authorization \
  --identity-validation-expression '^Bearer [-0-9a-zA-Z._]*$' \
  --authorizer-result-ttl-in-seconds 0 \
  --query 'id' \
  --output text \
  --region "$AWS_REGION")

for resource_id in "$CELLAR_PYTHON_RESOURCE_ID" "$CELLAR_NODE_RESOURCE_ID"; do
  aws apigateway update-method \
    --rest-api-id "$REST_API_ID" \
    --resource-id "$resource_id" \
    --http-method GET \
    --patch-operations \
      op=replace,path=/authorizationType,value=CUSTOM \
      op=replace,path=/authorizerId,value="$AUTH0_AUTHORIZER_ID" \
    --region "$AWS_REGION"
done
```

Allow API Gateway to invoke each Lambda:

```bash
for fn in "$AUTH0_AUTHORIZER_FUNCTION" "$PYTHON_CASK_FUNCTION" "$NODE_BARREL_FUNCTION" "$SOMMELIER_FUNCTION" "$AUTH_CALLBACK_FUNCTION" "$COGNITO_LOGOUT_FUNCTION" "$PYTHON_SIPPER_FUNCTION" "$NODE_SIPPER_FUNCTION"; do
  aws lambda add-permission \
    --function-name "$fn" \
    --statement-id "AllowExecutionFrom-${REST_API_ID}-${fn}" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${REST_API_ID}/*/*/*" \
    --region "$AWS_REGION"
done
```

Deploy the REST API:

```bash
aws apigateway create-deployment \
  --rest-api-id "$REST_API_ID" \
  --stage-name "$API_STAGE" \
  --description "Tawny Port REST deployment" \
  --region "$AWS_REGION"
```

---

# Testing

## 10. Validate The Deployment

Test public Table:

```bash
curl -i "${API_ENDPOINT}/table/sommelier"
```

Expected:

```text
HTTP 200 with Tawny Port Sommelier HTML.
```

Test Chalice before login:

```bash
curl -i "${API_ENDPOINT}/chalice/python-sipper"
curl -i "${API_ENDPOINT}/chalice/node-sipper"
```

Expected:

```text
HTTP 401 because no sessionId cookie exists yet.
```

Test Cellar without Auth0:

```bash
curl -i "${API_ENDPOINT}/cellar/python-cask"
```

Expected:

```text
HTTP 401 or 403.
```

Test Cellar with Auth0:

```bash
curl -i \
  -H "Authorization: Bearer ${AUTH0_TOKEN}" \
  "${API_ENDPOINT}/cellar/python-cask?name=Kirk"
```

Expected:

```text
HTTP 200 from the protected Cellar Lambda.
```

## 11. Validate Browser User Experience

Open this URL in a private browser window:

```text
https://<REST_API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier
```

Use the actual value:

```bash
echo "${API_ENDPOINT}/table/sommelier"
```

Validate the browser flow:

- Sommelier page loads.
- Python and Node login options send the browser to Cognito Managed Login.
- Cognito redirects back to `/prod/table/auth/callback`.
- `auth-callback` creates a DynamoDB session.
- The browser lands on the selected Chalice route.
- Refreshing the Chalice route works while the `sessionId` cookie is valid.
- Logout clears the cookie and returns to Sommelier.

---

# Operations

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Cognito says redirect mismatch | Callback URL differs from app client URL | Use `${API_ENDPOINT}/table/auth/callback` everywhere |
| Chalice route returns 401 after login | Session cookie missing or DynamoDB read failed | Check callback logs, sipper logs, cookie domain, and DynamoDB IAM |
| Cellar route returns 401 or 403 with token | Auth0 issuer, audience, dependency packaging, or authorizer binding mismatch | Inspect JWT `iss` and `aud`, authorizer logs, and PyJWT packaging |
| Lambda returns wrapped HTML JSON | Lambda proxy integration is disabled | Recreate or update the method integration as `AWS_PROXY` and redeploy |

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
| `zip` | [Info-ZIP manual](https://infozip.sourceforge.net/Zip.html) |


### AWS CLI References

| Command | AWS CLI reference |
| --- | --- |
| `aws sts get-caller-identity` | [sts get-caller-identity](https://docs.aws.amazon.com/cli/latest/reference/sts/get-caller-identity.html) |
| `aws dynamodb create-table` | [dynamodb create-table](https://docs.aws.amazon.com/cli/latest/reference/dynamodb/create-table.html) |
| `aws dynamodb wait table-exists` | [dynamodb wait table-exists](https://docs.aws.amazon.com/cli/latest/reference/dynamodb/wait/table-exists.html) |
| `aws dynamodb update-time-to-live` | [dynamodb update-time-to-live](https://docs.aws.amazon.com/cli/latest/reference/dynamodb/update-time-to-live.html) |
| `aws iam create-role` | [iam create-role](https://docs.aws.amazon.com/cli/latest/reference/iam/create-role.html) |
| `aws iam attach-role-policy` | [iam attach-role-policy](https://docs.aws.amazon.com/cli/latest/reference/iam/attach-role-policy.html) |
| `aws iam put-role-policy` | [iam put-role-policy](https://docs.aws.amazon.com/cli/latest/reference/iam/put-role-policy.html) |
| `aws iam get-role` | [iam get-role](https://docs.aws.amazon.com/cli/latest/reference/iam/get-role.html) |
| `aws lambda create-function` | [lambda create-function](https://docs.aws.amazon.com/cli/latest/reference/lambda/create-function.html) |
| `aws lambda get-function` | [lambda get-function](https://docs.aws.amazon.com/cli/latest/reference/lambda/get-function.html) |
| `aws apigateway create-rest-api` | [apigateway create-rest-api](https://docs.aws.amazon.com/cli/latest/reference/apigateway/create-rest-api.html) |
| `aws apigateway get-resources` | [apigateway get-resources](https://docs.aws.amazon.com/cli/latest/reference/apigateway/get-resources.html) |
| `aws cognito-idp create-user-pool` | [cognito-idp create-user-pool](https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/create-user-pool.html) |
| `aws cognito-idp create-user-pool-client` | [cognito-idp create-user-pool-client](https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/create-user-pool-client.html) |
| `aws cognito-idp describe-user-pool-client` | [cognito-idp describe-user-pool-client](https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/describe-user-pool-client.html) |
| `aws cognito-idp create-user-pool-domain` | [cognito-idp create-user-pool-domain](https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/create-user-pool-domain.html) |
| `aws lambda update-function-configuration` | [lambda update-function-configuration](https://docs.aws.amazon.com/cli/latest/reference/lambda/update-function-configuration.html) |
| `aws apigateway create-resource` | [apigateway create-resource](https://docs.aws.amazon.com/cli/latest/reference/apigateway/create-resource.html) |
| `aws apigateway put-method` | [apigateway put-method](https://docs.aws.amazon.com/cli/latest/reference/apigateway/put-method.html) |
| `aws apigateway put-integration` | [apigateway put-integration](https://docs.aws.amazon.com/cli/latest/reference/apigateway/put-integration.html) |
| `aws apigateway create-authorizer` | [apigateway create-authorizer](https://docs.aws.amazon.com/cli/latest/reference/apigateway/create-authorizer.html) |
| `aws apigateway update-method` | [apigateway update-method](https://docs.aws.amazon.com/cli/latest/reference/apigateway/update-method.html) |
| `aws lambda add-permission` | [lambda add-permission](https://docs.aws.amazon.com/cli/latest/reference/lambda/add-permission.html) |
| `aws apigateway create-deployment` | [apigateway create-deployment](https://docs.aws.amazon.com/cli/latest/reference/apigateway/create-deployment.html) |
