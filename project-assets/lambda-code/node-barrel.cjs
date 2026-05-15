// Node.js Lambda handler for public barrel endpoint
exports.handler = async (event) => {
    console.log("node-barrel request received");

    // Extract 'name' query parameter with fallback
    const name = event.queryStringParameters?.name || "Unknown";

    // Construct response message
    const response = {
        message: `WELCOME, ${name.toUpperCase()}. THE NODE BARREL AT TAWNY PORT IS AGED, TENDED, AND READY TO SERVE.`,
    };

    // Log outgoing response
    console.log("Response:", JSON.stringify(response));

    // Return HTTP 200 with JSON body
    return {
        statusCode: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(response),
    };
};
