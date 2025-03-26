# API Layout 
![alt text](../../static/api-layout.jpg)

## Example endpoint

```
POST /api/v1/calls
```
Start a new call session.

**Request Body:**
```json
{
  "phone_number": "string",
  "session_id": "string" (optional)
}
```

```
GET /api/v1/calls/{session_id}
```
Retrieve an existing call with session id.

**Query Parameters:**
- `recording_url` (optional): URL to recording
- `escalated` (optional): Whether call was escalated to human

## Africa's Talking Integration

The API now includes integration with Africa's Talking Voice services, allowing for inbound and outbound call handling, DTMF processing, and call event management.

### Voice Webhooks

```
POST /api/v1/voice
```
Primary webhook for handling incoming voice calls from Africa's Talking.

**Form Parameters:**
- `sessionId`: The unique session ID for the call
- `callerNumber`: The phone number of the caller
- `direction`: Direction of the call (inbound/outbound)
- `isActive`: Whether the call is active

```
POST /api/v1/dtmf
```
Webhook for handling DTMF (keypad) input from callers.

**Form Parameters:**
- `sessionId`: The unique session ID for the call
- `dtmfDigits`: The digits entered by the caller

```
POST /api/v1/events
```
Webhook for handling call events like hangup, transfer, etc.

**Form Parameters:**
- `sessionId`: The unique session ID for the call
- `status`: Current status of the call
- `durationInSeconds`: Duration of the call in seconds (for completed calls)

### Configuration

To use the Africa's Talking integration:

1. Set up your Africa's Talking account credentials in the `.env` file:
   ```
   AT_USER=your_username
   AT_API_KEY=your_api_key
   AT_PHONE=your_phone_number
   ```

2. Configure your webhook URLs in the Africa's Talking dashboard:
   - Voice URL: `{your_base_url}/api/v1/voice`
   - Events URL: `{your_base_url}/api/v1/events`
   - DTMF URL: `{your_base_url}/api/v1/dtmf`

3. For local development, use the `zeipo voice` command to set up a Cloudflare tunnel with public URLs.

## Response Formats

All API responses are in JSON format, except for Voice API webhooks which return XML.

### Transcription Response Example

```json
{
  "text": "Complete transcribed text",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Segment text"
    }
  ],
  "performance": {
    "process_time": 1.25,
    "audio_duration": 5.0,
    "real_time_factor": 0.25,
    "device": "cuda:0"
  }
}
```

### Voice Webhook Response Example

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Welcome to Zeipo AI. Your call has been received and is being processed.</Say>
</Response>
```

## Development Tools

Use the `zeipo` cli for common operations:

Ensure you've completed `Setting Up Your Environment` in the 
README.md found in the root directory of this project.

```powershell
# Build zeipo
zeipo build

# Start the API server
zeipo api

# Start with Africa's Talking integration and Cloudflare tunnel
zeipo voice

# Test GPU access
zeipo gpu

# Run tests
zeipo test

# View recent call logs
zeipo calls

# Help and information
zeipo help
```

## Interactive Documentation

When the API is running, visit `/docs` for interactive API documentation (Swagger UI).

## License

Copyright © 2025 Zeipo.ai - All Rights Reserved
