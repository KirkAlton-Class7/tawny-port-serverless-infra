import os
import json
import urllib.request
import urllib.parse
import base64
import uuid
import time
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['SESSION_TABLE'])

def decode_jwt_payload(token):
    """Decode JWT payload without signature verification."""
    parts = token.split('.')
    if len(parts) < 2:
        raise ValueError('Invalid JWT')
    payload = parts[1]
    padding = '=' * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding).decode('utf-8')
    return json.loads(decoded)

def lambda_handler(event, context):
    # Extract OAuth parameters
    qs = event.get('queryStringParameters', {}) or {}
    code = qs.get('code')
    incoming_state = qs.get('state')          # format: "python:random" or "node:random"
    error = qs.get('error')

    # Required configuration
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
    COGNITO_DOMAIN = os.environ['COGNITO_DOMAIN']
    REDIRECT_URI = os.environ['REDIRECT_URI']
    BASE_URL = os.environ.get('BASE_URL', 'https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/chalice')
    COOKIE_DOMAIN = os.environ.get('COOKIE_DOMAIN', '<API_ID>.execute-api.<AWS_REGION>.amazonaws.com')

    if error:
        return {'statusCode': 400, 'body': f'Authentication error: {error}'}
    if not code:
        return {'statusCode': 400, 'body': 'Missing code parameter'}
    if not incoming_state:
        return {'statusCode': 400, 'body': 'Missing state parameter'}

    # Validate composite state format
    parts = incoming_state.split(':', 1)
    if len(parts) != 2:
        return {'statusCode': 400, 'body': 'Invalid state format'}
    sipper, csrf_from_cognito = parts[0], parts[1]

    # CSRF protection: compare state cookie with state from Cognito
    cookies = event.get('cookies', [])
    expected_csrf = None
    for cookie_str in cookies:
        if cookie_str.startswith('oauth_state='):
            expected_csrf = cookie_str.split(';')[0].split('=', 1)[1]
            break

    if not expected_csrf or csrf_from_cognito != expected_csrf:
        print(f"CSRF mismatch: expected={expected_csrf}, got={csrf_from_cognito}")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/html'},
            'body': '''
            <!DOCTYPE html>
            <html>
            <head><title>Security Check Failed</title></head>
            <body style="font-family: Arial; text-align: center; margin-top: 50px;">
                <h2>Security Check Failed</h2>
                <p>There was a problem verifying your login request. This can happen if you refreshed the page or used the back button.</p>
                <p><a href="https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier">Click here to return to the Sommelier and try again</a></p>
            </body>
            </html>
            '''
        }

    # Exchange authorization code for tokens
    token_url = f'https://{COGNITO_DOMAIN}/oauth2/token'
    auth = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
    data = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }).encode()
    req = urllib.request.Request(token_url, data=data, method='POST')
    req.add_header('Authorization', f'Basic {auth}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read().decode())
            id_token = tokens.get('id_token')
            if not id_token:
                raise Exception('No id_token returned')
    except Exception as e:
        print(f'Token exchange error: {e}')
        return {'statusCode': 500, 'body': f'Token exchange failed: {str(e)}'}

    # Extract user claims from id_token (no signature verification, token obtained directly from Cognito)
    try:
        claims = decode_jwt_payload(id_token)
        user_email = claims.get('email', '')
        user_name = claims.get('cognito:username', user_email.split('@')[0] if user_email else 'unknown')
        if not user_email:
            user_email = 'unknown@example.com'
    except Exception as e:
        print(f'JWT decode error: {e}')
        return {'statusCode': 500, 'body': f'Failed to decode token: {str(e)}'}

    # Create session record in DynamoDB with 1-hour TTL
    session_id = str(uuid.uuid4())
    ttl = int(time.time()) + 3600
    try:
        table.put_item(Item={
            'sessionId': session_id,
            'userEmail': user_email,
            'userName': user_name,
            'expiresAt': ttl
        })
    except Exception as e:
        print(f'DynamoDB error: {e}')
        return {'statusCode': 500, 'body': f'Failed to create session: {str(e)}'}

    # Redirect to the selected sipper endpoint
    if sipper == 'python':
        location = f'{BASE_URL}/python-sipper'
    else:
        location = f'{BASE_URL}/node-sipper'

    # Clear CSRF state cookie and set session cookie
    return {
        'statusCode': 302,
        'headers': {
            'Location': location,
            'Set-Cookie': 'oauth_state=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT',
            'Set-Cookie': f'sessionId={session_id}; Domain={COOKIE_DOMAIN}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600'
        },
        'body': ''
    }
