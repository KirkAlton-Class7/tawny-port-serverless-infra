const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand } = require('@aws-sdk/lib-dynamodb');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);

exports.handler = async (event) => {
    let sessionId = null;

    // Extract sessionId from HTTP API cookies array
    if (event.cookies && Array.isArray(event.cookies)) {
        for (const cookieStr of event.cookies) {
            const parts = cookieStr.split(';');
            for (const part of parts) {
                const trimmed = part.trim();
                if (trimmed.startsWith('sessionId=')) {
                    sessionId = trimmed.substring('sessionId='.length);
                    break;
                }
            }
            if (sessionId) break;
        }
    } else {
        // Fallback for REST API Cookie header
        const cookieHeader = event.headers?.Cookie || event.headers?.cookie || '';
        if (cookieHeader) {
            const cookies = cookieHeader.split(';');
            for (const cookie of cookies) {
                const trimmed = cookie.trim();
                if (trimmed.startsWith('sessionId=')) {
                    sessionId = trimmed.substring('sessionId='.length);
                    break;
                }
            }
        }
    }

    if (!sessionId) {
        return {
            statusCode: 401,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'No session cookie' })
        };
    }

    const tableName = process.env.SESSION_TABLE;
    if (!tableName) {
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'SESSION_TABLE not configured' })
        };
    }

    try {
        const command = new GetCommand({
            TableName: tableName,
            Key: { sessionId: sessionId }
        });
        const result = await docClient.send(command);
        const item = result.Item;

        if (!item) {
            return {
                statusCode: 401,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'Invalid or expired session' })
            };
        }

        const userName = (item.userName || 'TAWNY PORT ENTHUSIAST').toUpperCase();

        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `SAÚDE, ${userName}! YOUR NODE SIPPER APP IS UNCORKED.`,
                timestamp: new Date().toISOString()
            })
        };
    } catch (err) {
        console.error('Session lookup error:', err);
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};