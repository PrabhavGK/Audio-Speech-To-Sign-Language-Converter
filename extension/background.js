// Listen for tab updates
browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && tab.url.includes('meet.google.com')) {
        console.log('Google Meet page loaded, injecting content script...');
        browser.tabs.executeScript(tabId, {
            file: 'content.js'
        }).catch(error => {
            console.error('Error injecting content script:', error);
        });
    }
});

// Handle messages from popup
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('Background received message:', message);
    
    if (message.action === 'startTranslation') {
        // Get the active tab
        browser.tabs.query({active: true, currentWindow: true}).then(tabs => {
            const activeTab = tabs[0];
            
            if (!activeTab.url.includes('meet.google.com')) {
                sendResponse({ error: 'Please open Google Meet first' });
                return;
            }
            
            // Send message to content script to start audio capture
            browser.tabs.sendMessage(activeTab.id, {
                action: 'startTranslation'
            }).then(response => {
                sendResponse(response);
            }).catch(error => {
                console.error('Error starting translation:', error);
                sendResponse({ error: 'Failed to start translation' });
            });
        });
        
        return true; // Keep the message channel open for async response
    }
    
    if (message.action === 'stopTranslation') {
        browser.tabs.query({active: true, currentWindow: true}).then(tabs => {
            const activeTab = tabs[0];
            browser.tabs.sendMessage(activeTab.id, {
                action: 'stopTranslation'
            }).then(response => {
                sendResponse(response);
            }).catch(error => {
                console.error('Error stopping translation:', error);
                sendResponse({ error: 'Failed to stop translation' });
            });
        });
        
        return true; // Keep the message channel open for async response
    }
    
    if (message.action === 'getStatus') {
        browser.tabs.query({active: true, currentWindow: true}).then(tabs => {
            const activeTab = tabs[0];
            browser.tabs.sendMessage(activeTab.id, {
                action: 'getStatus'
            }).then(response => {
                sendResponse(response);
            }).catch(error => {
                console.error('Error getting status:', error);
                sendResponse({ error: 'Failed to get status' });
            });
        });
        
        return true; // Keep the message channel open for async response
    }
}); 