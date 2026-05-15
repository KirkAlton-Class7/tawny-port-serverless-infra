import json
import os
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['SESSION_TABLE'])

def lambda_handler(event, context):
    session_id = None

    # Extract sessionId from HTTP API cookies array
    if 'cookies' in event:
        for cookie_str in event.get('cookies', []):
            for part in cookie_str.split(';'):
                part = part.strip()
                if part.startswith('sessionId='):
                    session_id = part.split('=', 1)[1]
                    break
    else:
        # Fallback for REST API Cookie header
        cookies = event.get('headers', {}).get('Cookie', '')
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('sessionId='):
                session_id = cookie.split('=', 1)[1]
                break

    if not session_id:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'No session cookie'})
        }

    try:
        resp = table.get_item(Key={'sessionId': session_id})
        item = resp.get('Item')
        if not item:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid session'})
            }
        user_name = item.get('userName', 'TAWNY PORT ENTHUSIAST').upper()
    except Exception as e:
        print(f"Session lookup error: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'message': f'CHEERS, {user_name}! YOUR PYTHON SIPPER APP IS UNCORKED.',
            'timestamp': datetime.utcnow().isoformat()
        })
    }