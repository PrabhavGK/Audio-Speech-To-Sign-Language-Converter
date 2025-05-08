document.addEventListener('DOMContentLoaded', function() {
  const toggleButton = document.getElementById('toggleButton');
  const statusDiv = document.getElementById('status');
  let isActive = false;

  // Load saved state
  chrome.storage.local.get(['isActive'], function(result) {
    isActive = result.isActive || false;
    updateUI();
  });

  toggleButton.addEventListener('click', function() {
    isActive = !isActive;
    
    // Save state
    chrome.storage.local.set({ isActive: isActive });
    
    // Send message to content script
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      chrome.tabs.sendMessage(tabs[0].id, {
        action: isActive ? 'startTranslation' : 'stopTranslation'
      });
    });

    updateUI();
  });

  function updateUI() {
    if (isActive) {
      toggleButton.textContent = 'Stop Translation';
      statusDiv.textContent = 'Status: Active';
      statusDiv.classList.add('active');
    } else {
      toggleButton.textContent = 'Start Translation';
      statusDiv.textContent = 'Status: Inactive';
      statusDiv.classList.remove('active');
    }
  }
}); 