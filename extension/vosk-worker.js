// Import Vosk WASM module
importScripts('https://cdn.jsdelivr.net/npm/vosk-browser@0.0.7/dist/vosk.js');

let model = null;
let recognizer = null;

// Initialize Vosk model
async function initVosk() {
    if (!model) {
        try {
            // Load the small English model (about 40MB)
            const response = await fetch('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip');
            const modelData = await response.arrayBuffer();
            model = new Vosk.Model(modelData);
            recognizer = new Vosk.Recognizer({model: model, sampleRate: 16000});
        } catch (error) {
            console.error('Error initializing Vosk:', error);
            postMessage({type: 'error', error: 'Failed to initialize speech recognition'});
        }
    }
}

// Process audio data
async function processAudio(audioData) {
    try {
        if (!recognizer) {
            await initVosk();
        }
        
        // Process audio in chunks
        const chunkSize = 4096;
        const int16Data = new Int16Array(audioData);
        
        for (let i = 0; i < int16Data.length; i += chunkSize) {
            const chunk = int16Data.slice(i, i + chunkSize);
            recognizer.acceptWaveform(chunk);
        }
        
        // Get final result
        const result = recognizer.finalResult();
        postMessage({type: 'result', text: result.text});
        
    } catch (error) {
        console.error('Error processing audio:', error);
        postMessage({type: 'error', error: 'Failed to process audio'});
    }
}

// Handle messages from main thread
self.onmessage = function(e) {
    if (e.data.type === 'process') {
        processAudio(e.data.audioData);
    }
}; 