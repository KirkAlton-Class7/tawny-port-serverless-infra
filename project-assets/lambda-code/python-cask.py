import json
from datetime import datetime

# Python Lambda handler for public cask endpoint
def lambda_handler(event, context):
    # Log incoming request for debugging
    print("Incoming event:", json.dumps(event))

    # Extract 'name' query parameter with fallback
    name = event.get("queryStringParameters", {}).get("name", "Unknown")

    # Construct response message
    response = {
        "message": f"Welcome, {name}. The Python Cask at Tawny Port is tapped, tended, and ready to serve.",
        "timestamp": datetime.utcnow().isoformat()
    }

    # Log outgoing response
    print("Response:", json.dumps(response))

    # Return HTTP 200 with JSON body
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response)
    }