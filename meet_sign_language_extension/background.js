// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('Sign Language for Google Meet extension installed');
});

// Handle messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'updateStatus') {
    // Update extension icon or badge if needed
  }
}); 