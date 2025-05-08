// Global state
let isActive = false;
let audioContext = null;
let mediaStream = null;
let audioSource = null;
let processor = null;

// Handle messages from popup
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('Content script received message:', message);
    
    if (message.action === 'startTranslation') {
        if (isActive) {
            sendResponse({ error: 'Translation is already active' });
            return;
        }
        
        handleAudioCapture()
            .then(() => {
                isActive = true;
                sendResponse({ success: true });
            })
            .catch(error => {
                console.error('Error starting audio capture:', error);
                sendResponse({ error: error.message });
            });
        
        return true; // Keep the message channel open for async response
    }
    
    if (message.action === 'stopTranslation') {
        stopAudioCapture();
        isActive = false;
        sendResponse({ success: true });
        return true;
    }
    
    if (message.action === 'getStatus') {
        sendResponse({ isActive });
        return true;
    }
});

// Function to handle audio capture
async function handleAudioCapture() {
    try {
        // Request microphone access
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Create audio context
        audioContext = new AudioContext();
        audioSource = audioContext.createMediaStreamSource(mediaStream);
        
        // Create processor node
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        
        // Connect nodes
        audioSource.connect(processor);
        processor.connect(audioContext.destination);
        
        // Process audio data
        processor.onaudioprocess = async (e) => {
            if (!isActive) return;
            
            const inputData = e.inputBuffer.getChannelData(0);
            const audioBlob = await convertAudioToBlob(inputData);
            
            // Send audio data to backend
            try {
                const formData = new FormData();
                formData.append('audio', audioBlob, 'audio.wav');
                
                const response = await fetch('http://localhost:8000/transcribe/', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error('Failed to transcribe audio');
                }
                
                const data = await response.json();
                
                // Send response back to popup
                browser.runtime.sendMessage({
                    type: 'sign_language_response',
                    data: data
                });
            } catch (error) {
                console.error('Error processing audio:', error);
                browser.runtime.sendMessage({
                    type: 'sign_language_response',
                    data: { error: 'Failed to process audio' }
                });
            }
        };
    } catch (error) {
        console.error('Error in handleAudioCapture:', error);
        throw new Error('Failed to access microphone');
    }
}

// Function to stop audio capture
function stopAudioCapture() {
    if (processor) {
        processor.disconnect();
        processor = null;
    }
    
    if (audioSource) {
        audioSource.disconnect();
        audioSource = null;
    }
    
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
}

// Function to convert audio data to blob
async function convertAudioToBlob(audioData) {
    const wavBlob = new Blob([audioData], { type: 'audio/wav' });
    return wavBlob;
}

// Initialize when the page loads
window.addEventListener('load', () => {
    console.log('Content script loaded');
    // Check if we're on a Google Meet page
    if (window.location.hostname.includes('meet.google.com')) {
        console.log('Google Meet page detected');
        // Wait for the page to be fully loaded
        setTimeout(() => {
            handleAudioCapture();
        }, 2000);
    }
}); 