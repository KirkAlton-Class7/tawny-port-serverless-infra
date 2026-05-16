import json
import os
import boto3
import urllib.parse

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['SESSION_TABLE'])

def lambda_handler(event, context):
    session_id = None

    # Extract sessionId from the REST API Lambda proxy Cookie header.
    cookies = (
        event.get('headers', {}).get('Cookie')
        or event.get('headers', {}).get('cookie')
        or ''
    )
    for cookie in cookies.split(';'):
        cookie = cookie.strip()
        if cookie.startswith('sessionId='):
            session_id = cookie.split('=', 1)[1]
            break

    # Compatibility fallback if the function is later tested with HTTP API events.
    if not session_id and 'cookies' in event:
        for cookie_str in event.get('cookies', []):
            parts = cookie_str.split(';')
            for part in parts:
                part = part.strip()
                if part.startswith('sessionId='):
                    session_id = part.split('=', 1)[1]
                    break
            if session_id:
                break

    # Delete session from DynamoDB with existence check and verification
    if session_id:
        try:
            resp = table.get_item(Key={'sessionId': session_id})
            if 'Item' in resp:
                print("Found session to delete")
                table.delete_item(Key={'sessionId': session_id})
                verify = table.get_item(Key={'sessionId': session_id})
                if 'Item' not in verify:
                    print("Session successfully deleted")
                else:
                    print("WARNING: Session still exists after delete")
            else:
                print("Session not found in DynamoDB")
        except Exception as e:
            print(f"Failed to delete session: {e}")
    else:
        print("No sessionId cookie found – nothing to delete")

    # Environment configuration
    cognito_domain = os.environ['COGNITO_DOMAIN']
    client_id = os.environ['CLIENT_ID']
    cookie_domain = os.environ.get('COOKIE_DOMAIN', '<API_ID>.execute-api.<AWS_REGION>.amazonaws.com')
    base_sommelier = os.environ.get('POST_LOGOUT_REDIRECT_URI',
                                    'https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/sommelier')

    # Build Cognito logout URL with state parameter for optional confirmation
    encoded_redirect = urllib.parse.quote(base_sommelier, safe='')
    logout_url = (f'https://{cognito_domain}/logout'
                  f'?client_id={client_id}'
                  f'&logout_uri={encoded_redirect}'
                  f'&state=logout_success')

    # Clear session cookie using same attributes as when set
    clear_cookie = (f'sessionId=; Domain={cookie_domain}; Path=/; '
                    f'HttpOnly; Secure; SameSite=Lax; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT')

    # Redirect to Cognito logout endpoint
    return {
        'statusCode': 302,
        'headers': {
            'Location': logout_url,
            'Set-Cookie': clear_cookie
        },
        'body': ''
    }
