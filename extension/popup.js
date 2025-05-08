// Get DOM elements
const statusDiv = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const animationContainer = document.getElementById('animationContainer');

// Function to update status
function updateStatus(isActive) {
    statusDiv.className = `status ${isActive ? 'active' : 'inactive'}`;
    statusDiv.textContent = `Status: ${isActive ? 'Active' : 'Inactive'}`;
    startBtn.disabled = isActive;
    stopBtn.disabled = !isActive;
}

// Function to handle sign language response
function handleSignLanguageResponse(data) {
    // Clear previous content
    animationContainer.innerHTML = '';
    
    if (data.error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = data.error;
        animationContainer.appendChild(errorDiv);
        return;
    }
    
    // Display recognized text
    const textDiv = document.createElement('div');
    textDiv.className = 'text';
    textDiv.innerHTML = `<strong>Recognized Text:</strong> ${data.text}`;
    animationContainer.appendChild(textDiv);
    
    // Display missing videos if any
    if (data.missing_videos) {
        const missingDiv = document.createElement('div');
        missingDiv.className = 'missing-videos';
        missingDiv.innerHTML = `
            <strong>Missing Animations:</strong>
            <ul>
                ${data.missing_videos.map(video => `<li>${video}</li>`).join('')}
            </ul>
        `;
        animationContainer.appendChild(missingDiv);
    }
    
    // Display videos
    data.words.forEach(word => {
        const videoDiv = document.createElement('div');
        videoDiv.className = 'video-container';
        videoDiv.innerHTML = `
            <video controls>
                <source src="${word}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        `;
        animationContainer.appendChild(videoDiv);
    });
}

// Function to send message to content script with retry
async function sendMessageToContentScript(message, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const tabs = await browser.tabs.query({active: true, currentWindow: true});
            if (tabs.length === 0) {
                throw new Error('No active tab found');
            }
            
            // Check if we're on a Google Meet page
            if (!tabs[0].url.includes('meet.google.com')) {
                throw new Error('Please navigate to a Google Meet page');
            }
            
            const response = await browser.tabs.sendMessage(tabs[0].id, message);
            if (response.error) {
                throw new Error(response.error);
            }
            return response;
        } catch (error) {
            console.error(`Attempt ${i + 1} failed:`, error);
            
            if (i === retries - 1) {
                // Last attempt failed
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.textContent = 'Error: ' + error.message + '. Please refresh the page and try again.';
                animationContainer.appendChild(errorDiv);
                updateStatus(false);
                throw error;
            }
            
            // Wait before retrying
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
}

// Event listeners
startBtn.addEventListener('click', async () => {
    try {
        // Send message to content script to start translation
        await sendMessageToContentScript({action: 'startTranslation'});
        updateStatus(true);
    } catch (error) {
        console.error('Error starting translation:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Error: ' + error.message;
        animationContainer.appendChild(errorDiv);
        updateStatus(false);
    }
});

stopBtn.addEventListener('click', async () => {
    try {
        // Send message to content script to stop translation
        await sendMessageToContentScript({action: 'stopTranslation'});
        updateStatus(false);
    } catch (error) {
        console.error('Error stopping translation:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Error: ' + error.message;
        animationContainer.appendChild(errorDiv);
    }
});

// Listen for messages from content script
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'sign_language_response') {
        handleSignLanguageResponse(message.data);
    }
});

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Check if translation is already active
        const response = await sendMessageToContentScript({action: 'getStatus'});
        if (response && response.isActive) {
            updateStatus(true);
        }
    } catch (error) {
        console.error('Error initializing popup:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = 'Error: ' + error.message;
        animationContainer.appendChild(errorDiv);
    }
}); 