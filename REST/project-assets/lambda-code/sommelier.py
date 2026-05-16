import os
import json
import urllib.parse
import secrets

def lambda_handler(event, context):
    print("sommelier request received")

    # Environment configuration
    CLIENT_ID = os.environ.get("CLIENT_ID")
    COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN")
    CALLBACK_REDIRECT_URI = os.environ.get(
        "CALLBACK_REDIRECT_URI",
        "https://<API_ID>.execute-api.<AWS_REGION>.amazonaws.com/prod/table/auth/callback"
    )

    # Logout success detection via state parameter echoed by Cognito
    query_params = event.get("queryStringParameters", {}) or {}
    state_param = query_params.get("state")
    logout_message = ""
    if state_param == "logout_success":
        logout_message = """
        <div class="logout-message">
            Successfully logged out.
        </div>
        """

    # Validate required environment variables
    if not CLIENT_ID or not COGNITO_DOMAIN:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Missing Lambda environment variables",
                "required": ["CLIENT_ID", "COGNITO_DOMAIN"]
            })
        }

    # CSRF protection: random state stored in HttpOnly cookie, 5 min TTL
    csrf_state = secrets.token_urlsafe(16)
    state_cookie = f"oauth_state={csrf_state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=300"

    def build_login_url(redirect_uri, sipper):
        """Construct Cognito Hosted UI login URL with composite state (sipper:csrf)."""
        composite_state = f"{sipper}:{csrf_state}"
        return (
            f"https://{COGNITO_DOMAIN}/login"
            f"?client_id={CLIENT_ID}"
            f"&response_type=code"
            f"&scope=openid+email+phone"
            f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
            f"&state={urllib.parse.quote(composite_state, safe='')}"
        )

    node_login_url = build_login_url(CALLBACK_REDIRECT_URI, "node")
    python_login_url = build_login_url(CALLBACK_REDIRECT_URI, "python")

    # HTML Sommelier page with inline styles
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tawny Port Sommelier</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0F1B2A;
            color: #F7E7CE;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            text-align: center;
        }}

        .container {{
            background: rgba(15, 27, 42, 0.92);
            border: 1px solid #6d5f2c;
            padding: 50px;
            border-radius: 16px;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.42);
            max-width: 700px;
            width: 90%;
        }}

        h1 {{
            color: #F7E7CE;
            margin-bottom: 12px;
        }}

        p {{
            color: rgba(247, 231, 206, 0.72);
            margin-bottom: 35px;
        }}

        .button-group {{
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}

        .port-button {{
            display: inline-block;
            text-decoration: none;
            padding: 16px 24px;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            transition: all 0.2s ease;
        }}

        .node {{
            background: #570505;
            color: #F7E7CE;
            border: 1px solid #570505;
        }}

        .node:hover {{
            background: #7A0B0B;
            color: #FFF4E3;
        }}

        .python {{
            background: #0F1B2A;
            color: #F7E7CE;
            border: 1px solid #570505;
        }}

        .python:hover {{
            background: #570505;
            color: #F4D35E;
            border-color: #F7E7CE;
        }}

        .footer {{
            margin-top: 30px;
            font-size: 14px;
            color: rgba(247, 231, 206, 0.52);
        }}

        .logout-message {{
            background: #2E5D3A;
            color: #FFFFFF;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 25px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Welcome to Port Connoisseur</h1>
        <p>Select your preferred Tawny Port experience.</p>
        {logout_message}
        <div class="button-group">
            <a class="port-button node" href="{node_login_url}">Node Sipper</a>
            <a class="port-button python" href="{python_login_url}">Python Sipper</a>
        </div>
        <div class="footer">Cellar &gt; Table &gt; Sommelier &gt; Chalice</div>
    </div>
</body>
</html>
"""

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html",
            "Set-Cookie": state_cookie
        },
        "body": html
    }
