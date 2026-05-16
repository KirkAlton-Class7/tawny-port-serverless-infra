# Lambda Code Packaging

Use this folder as the source for the REST API Lambda functions. Most route handlers can be pasted directly into the Lambda console. The Auth0 authorizer is different because it imports `jwt` from PyJWT, which AWS Lambda does not include by default.

## Console Paste Functions

These functions can be pasted directly into the Lambda console because they use the runtime libraries already available to the function:

| Function | Source file | Runtime |
| --- | --- | --- |
| `sommelier` | `sommelier.py` | Python |
| `auth-callback` | `auth-callback.py` | Python |
| `cognito-logout` | `cognito-logout.py` | Python |
| `python-sipper` | `python-sipper.py` | Python |
| `python-cask` | `python-cask.py` | Python |
| `node-sipper` | `node-sipper.cjs` | Node.js 20.x |
| `node-barrel` | `node-barrel.cjs` | Node.js 20.x |

For Python functions, paste the code into the Lambda console's default module file and set the handler to match that file:

```text
lambda_function.lambda_handler
```

For Node.js `.cjs` functions, set the handler to match the file name used in the console:

```text
index.handler
```

Click **Deploy** if prompted.

## Auth0 JWT Authorizer Package

`auth0-jwt-authorizer.py` requires PyJWT:

```python
import jwt
```

Pasting only the Python file into Lambda will cause this error unless PyJWT is packaged or provided by a layer:

```text
No module named 'jwt'
```

Build a ZIP package:

```bash
cd REST/project-assets/lambda-code

mkdir -p auth0-authorizer-build
cp auth0-jwt-authorizer.py auth0-authorizer-build/lambda_function.py
python3 -m pip install -r requirements-auth0-jwt-authorizer.txt -t auth0-authorizer-build

cd auth0-authorizer-build
zip -r ../auth0-jwt-authorizer.zip .
```

`auth0-authorizer-build/` is a temporary local packaging directory. It does not need to be committed when `auth0-jwt-authorizer.zip` is already present.

Upload the package:

1. Open the `auth0-jwt-authorizer` Lambda.
2. Go to **Code**.
3. Choose **Upload from**.
4. Select **.zip file**.
5. Upload `auth0-jwt-authorizer.zip`.
6. Set the handler to either:

```text
lambda_function.handler
```

or:

```text
lambda_function.lambda_handler
```

The packaged authorizer exposes both entrypoints.

Click **Deploy** if prompted.

## Common Packaging Errors

| Error | Cause | Fix |
| --- | --- | --- |
| `No module named 'jwt'` | PyJWT was not packaged or layered | Upload the ZIP package or attach a layer with `PyJWT[crypto]` |
| `cryptography` import error | Package was built for an incompatible platform | Rebuild on Amazon Linux or use a compatible Lambda layer |
| `Unable to import module` | Handler file name does not match Lambda handler setting | Use `lambda_function.py` with `lambda_function.lambda_handler` |