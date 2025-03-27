// zeipo_handler.js
// This script handles calls in the SignalWire/FreeSWITCH environment
// and communicates with the Zeipo API for AI processing

// Get session details
var sessionId = session.getVariable("session_id");
var direction = session.getVariable("direction") || "inbound";
var callerNumber = session.getVariable("caller_id_number");

// Log call start
console.log("Handling call: " + sessionId + " from " + callerNumber);

// Initialize TTS and STT
function speak(text) {
    session.execute("speak", "flite|slt|" + text);
}

// Get initial welcome message
speak("Welcome to Zeipo AI. How can I help you today?");

// Set up speech recognition
session.execute("detect_speech", "pocketsphinx yes");
session.setVariable("detect_speech_result", "zeipo_stt_result");

// Main call loop
while (session.ready()) {
    // Wait for input or timeout
    var result = session.getDigits(1, "", 30000);
    
    if (result === '') {
        // No DTMF, check for speech
        var speechResult = session.getVariable("zeipo_stt_result");
        if (speechResult && speechResult !== '') {
            // Process speech through Zeipo API
            var apiUrl = "http://core:8000/api/v1/nlu/process";
            var params = {
                text: speechResult,
                session_id: sessionId
            };
            
            try {
                var response = fetchUrl(apiUrl, JSON.stringify(params), {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    }
                });
                
                var apiResponse = JSON.parse(response);
                
                // Speak the response
                if (apiResponse && apiResponse.response) {
                    speak(apiResponse.response);
                } else {
                    speak("I'm sorry, I didn't understand that. Can you please try again?");
                }
            } catch (e) {
                console.log("API Error: " + e.message);
                speak("I'm having trouble processing that request. Please try again later.");
            }
            
            // Reset speech detection
            session.execute("detect_speech", "pocketsphinx stop");
            session.execute("detect_speech", "pocketsphinx yes");
        }
    } else {
        // Handle DTMF input
        console.log("DTMF Input: " + result);
        
        // Process DTMF through Zeipo API
        // (Implementation similar to speech processing)
    }
    
    // Check if call is still active
    if (!session.ready()) {
        break;
    }
}

// Log call end
console.log("Call ended: " + sessionId);
