# Zeipo Telephony Layer

This repository contains the Asterisk configuration for Zeipo's telephony layer, providing low-latency voice communication infrastructure for Zeipo AI platform.

## Overview

The Zeipo telephony layer serves as the foundation for voice communication between callers and the core system, responsible for:

- Inbound call routing from SIP trunks
- Call recording and monitoring
- Integration with Zeipo AI via Asterisk REST Interface (ARI)
- Outbound calling capabilities
- WebRTC client connectivity
- Low-latency media processing

## Architecture

The system is built on Asterisk with a focus on the Stasis application framework and ARI integration. Key components:

![alt text](../../static/telephony-layer.jpg)

1. **Asterisk PBX**: Central Private Branch Exchange for voice processing 
2. **ARI (Asterisk REST Interface)**: API allowing Zeipo AI to control calls
3. **Stasis Application**: Framework for programmatically controlling calls
4. **SIP Trunking**: Connection to Africa's Talking for PSTN access
5. **RTP Media Engine**: Low-latency voice packet transmission
6. **Call Recording**: Automatic recording for all interactions

## Configuration Files

| File | Purpose |
|------|---------|
| `ari.conf` | Configures Asterisk REST Interface for AI integration |
| `extensions.conf` | Dialplan defining call routing and handling logic |
| `http.conf` | HTTP/WebSocket server settings for ARI and WebRTC |
| `modules.conf` | Required Asterisk modules for our implementation |
| `pjsip.conf` | SIP endpoint and trunk configuration |
| `rtp.conf` | Media handling and NAT traversal settings |

## Prerequisites

- Asterisk 20+
- Publicly accessible server with static IP
- SIP trunk account with Africa's Talking
- Open ports:
  - 5060 (SIP)
  - 8088 (HTTP/WebSocket)
  - 10000-20000 (RTP media)

## Installation

Asterisk is pre configured in the Docker container. 
Find it's config files in the `config/asterisk/config` folder.

## Usage

### Accessing the Zeipo AI System

Users can access the Zeipo AI system through:

1. **Direct Dial**: Calling a number provisioned on Africa's Talking
2. **Extension Access**: Dialing extension 9000 from an internal SIP device
3. **WebRTC**: Connecting via web client

### Outbound Calling

To make outbound calls:

1. Dial a number prefixed with "0" from any registered SIP extension
2. The system routes the call through Africa's Talking
3. Caller ID is set to "Zeipo AI" with number 254700000000

### Testing and Debugging

Monitor active calls:
```bash
asterisk -rx "core show channels"
```

Watch Asterisk logs:
```bash
tail -f /var/log/asterisk/full
```

Test ARI connection:
```bash
curl -v "http://localhost:8088/ari/applications?api_key=zeipo:${ASTERISK_ARI_PASSWORD}"
```

## Development

### Connecting with ARI

The Zeipo AI application connects to Asterisk using WebSockets:

```javascript
const client = ari.Client(
  'http://localhost:8088',
  'zeipo',
  process.env.ASTERISK_ARI_PASSWORD
);

client.on('StasisStart', handleStasisStart);
client.start('zeipo');
```

### Call Flow

1. Incoming call arrives via SIP trunk
2. Call is answered and passed to Stasis(`zeipo`)
3. Zeipo AI application receives StasisStart event
4. AI application controls call via ARI commands
5. Call is recorded throughout the conversation

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| ARI Connection Failures | Check `http.conf` settings and firewall rules for port 8088 |
| Trunk Registration Issues | Verify Africa's Talking credentials in `pjsip.conf` |
| One-way Audio | Check NAT settings and STUN server access |
| High Latency | Review codec selection and RTP configuration |
| Call Recording Failures | Check directory permissions and disk space |

## Low Latency Optimizations

This configuration is optimized for low latency voice:

- Standard ulaw/alaw codecs for reliable, low-latency audio
- ICE/STUN for optimal media path selection
- WebSocket keep-alive settings tuned for responsiveness
- Strategic media handling settings in `pjsip.conf`

## Integration with Other Zeipo Components

The telephony layer integrates with other Zeipo systems:

- **Speech Recognition**: Call audio is processed by the Whisper integration
- **NLP/NLU**: Text from speech recognition is processed to determine intent
- **AI Application**: Controls call flow based on recognized intents

For more details on these components, refer to their respective repositories:
- [API Integration](../api/README.md)
- [NLP System](../nlp/README.md)
- [NLU System](../nlu/README.md)

## License

Copyright © 2025 Zeipo.ai - All Rights Reserved