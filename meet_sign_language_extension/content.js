let mediaRecorder = null;
let audioContext = null;
let audioChunks = [];
let isRecording = false;
let silenceTimer = null;
const SILENCE_THRESHOLD = 0.01;
const SILENCE_DURATION = 1000; // 1 second of silence to stop recording

// Create and inject the sign language display container
function createDisplayContainer() {
  const container = document.createElement('div');
  container.id = 'sign-language-container';
  container.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 300px;
    height: 200px;
    background: rgba(0, 0, 0, 0.8);
    border-radius: 8px;
    z-index: 9999;
    display: none;
  `;
  document.body.appendChild(container);
  return container;
}

// Initialize audio processing
async function initializeAudio() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      } 
    });

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = handleAudioData;
    mediaRecorder.onstop = processAudio;

    return true;
  } catch (error) {
    console.error('Error initializing audio:', error);
    return false;
  }
}

// Handle incoming audio data
function handleAudioData(event) {
  audioChunks.push(event.data);
}

// Process recorded audio
async function processAudio() {
  const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
  audioChunks = [];

  // Convert audio to text using Web Speech API
  const text = await convertAudioToText(audioBlob);
  if (text) {
    // Send text to your Django backend for sign language conversion
    const response = await fetch('http://localhost:8000/animation/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: text })
    });

    if (response.ok) {
      const data = await response.json();
      displaySignLanguage(data.videos);
    }
  }
}

// Convert audio to text using Web Speech API
async function convertAudioToText(audioBlob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = function() {
      const audioData = reader.result;
      const recognition = new webkitSpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onresult = function(event) {
        const text = event.results[0][0].transcript;
        resolve(text);
      };

      recognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        resolve(null);
      };

      recognition.start();
    };
    reader.readAsDataURL(audioBlob);
  });
}

// Display sign language animations
function displaySignLanguage(videos) {
  const container = document.getElementById('sign-language-container') || createDisplayContainer();
  container.style.display = 'block';

  // Clear previous content
  container.innerHTML = '';

  // Create video element
  const video = document.createElement('video');
  video.style.width = '100%';
  video.style.height = '100%';
  video.style.objectFit = 'contain';
  container.appendChild(video);

  // Play videos in sequence
  let currentIndex = 0;
  function playNextVideo() {
    if (currentIndex < videos.length) {
      const videoPath = `/assets/${videos[currentIndex]}.mp4`;
      video.src = videoPath;
      video.play();
      currentIndex++;
    } else {
      container.style.display = 'none';
    }
  }

  video.addEventListener('ended', playNextVideo);
  playNextVideo();
}

// Start recording
function startRecording() {
  if (!isRecording) {
    isRecording = true;
    mediaRecorder.start(100);
    silenceTimer = setInterval(checkSilence, 100);
  }
}

// Stop recording
function stopRecording() {
  if (isRecording) {
    isRecording = false;
    mediaRecorder.stop();
    clearInterval(silenceTimer);
  }
}

// Check for silence
function checkSilence() {
  const analyser = audioContext.analyser;
  const dataArray = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(dataArray);
  
  const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
  if (average < SILENCE_THRESHOLD) {
    stopRecording();
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'startTranslation') {
    initializeAudio().then(success => {
      if (success) {
        startRecording();
      }
    });
  } else if (request.action === 'stopTranslation') {
    stopRecording();
  }
}); 