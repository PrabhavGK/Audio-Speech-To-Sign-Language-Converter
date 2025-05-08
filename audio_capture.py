import sounddevice as sd
import numpy as np
import requests
import threading
import queue
import time
import wave
import tempfile
import os
import sys
import logging
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import argparse
import subprocess
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoDisplayServer(threading.Thread):
    def __init__(self, port=8002):
        super().__init__()
        self.port = port
        self.server = None
        self.daemon = True  # Thread will exit when main program exits
        
    def run(self):
        try:
            self.server = HTTPServer(('localhost', self.port), SimpleHTTPRequestHandler)
            logger.info(f"Starting video display server on port {self.port}")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting video server: {e}")
            
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

class AudioCapture:
    def __init__(self, sample_rate=16000, channels=1, allow_mic=False):
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stream = None
        self.video_server = VideoDisplayServer()
        self.video_server.start()
        self.current_browser_tab = None
        self.html_file_path = os.path.join('static', 'videos.html')
        self.last_update_time = time.time()
        self.allow_mic = allow_mic
        self.gmeet_active = False
        self.last_gmeet_check = 0
        self.own_voice_threshold = 0.45  # Threshold to identify user's own voice (higher values)
        
        # Create static directory if it doesn't exist
        os.makedirs('static', exist_ok=True)
        
        # Initialize with empty HTML page
        self.initialize_html_page()
        
    def check_google_meet_active(self):
        """Check if Google Meet is currently running"""
        # Only check every 5 seconds to avoid constant process checking
        current_time = time.time()
        if current_time - self.last_gmeet_check < 5:
            return self.gmeet_active
        
        self.last_gmeet_check = current_time
        
        # For testing purposes, always return True
        self.gmeet_active = True
        logger.info(f"Google Meet active: {self.gmeet_active} (FORCED ACTIVE for testing)")
        return self.gmeet_active
        
        # Original detection code below (commented out)
        """
        try:
            # Check running processes for Google Meet (browser)
            if sys.platform == 'linux' or sys.platform == 'linux2':
                try:
                    # Use ps and grep to find Google Meet processes
                    cmd = "ps aux | grep -E 'meet.google.com' | grep -v grep"
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    # Also check if a browser tab with meet.google.com is open
                    cmd2 = "ps aux | grep -E 'chrome|firefox|brave|edge' | grep -v grep"
                    browser_result = subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    has_meet = 'meet.google.com' in result.stdout
                    
                    # For browsers, we'll check if there's output and if we find any mention of Meet
                    browser_running = len(browser_result.stdout) > 0
                    
                    self.gmeet_active = has_meet and browser_running
                    
                except Exception as e:
                    logger.error(f"Error checking for Google Meet on Linux: {e}")
                    # Default to assume it's active if checking fails
                    self.gmeet_active = True
            
            elif sys.platform == 'darwin':  # macOS
                try:
                    cmd = "ps -ef | grep -E 'meet.google.com' | grep -v grep"
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    self.gmeet_active = 'meet.google.com' in result.stdout
                except Exception as e:
                    logger.error(f"Error checking for Google Meet on macOS: {e}")
                    self.gmeet_active = True
            
            elif sys.platform == 'win32':  # Windows
                try:
                    cmd = "tasklist /FI \"WINDOWTITLE eq *meet.google*\" /FO CSV"
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    self.gmeet_active = len(result.stdout.splitlines()) > 1  # More than header means tasks found
                except Exception as e:
                    logger.error(f"Error checking for Google Meet on Windows: {e}")
                    self.gmeet_active = True
                    
            # Default to active if we can't determine
            else:
                self.gmeet_active = True
                
            logger.info(f"Google Meet active: {self.gmeet_active}")
            return self.gmeet_active
            
        except Exception as e:
            logger.error(f"Error checking for Google Meet: {e}")
            # Default to assume it's active if checking fails
            self.gmeet_active = True
            return self.gmeet_active
        """
        
    def initialize_html_page(self):
        """Create initial HTML page for words"""
        mic_status = "ALLOWED" if self.allow_mic else "BLOCKED"
        audio_source = "System Audio + Microphone" if self.allow_mic else "System Audio ONLY (Google Meet)"
        gmeet_status = "ACTIVE" if self.check_google_meet_active() else "INACTIVE"
        
        # Initialize empty variables for first load
        text = ""
        formatted_words = []
        videos = []
        sentences = []

        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Sign Language Translator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f0f0; padding-bottom: 20px; }}
        .transcription {{ background-color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 18px; }}
        .word-container {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                          padding: 20px; margin-bottom: 15px; text-align: center; width: 100%; max-width: 600px; }}
        .stack-container {{ display: flex; flex-direction: column-reverse; align-items: center; width: 100%; }}
        .word {{ font-weight: bold; font-size: 2em; color: #333; padding: 10px; }}
        .video-container {{ width: 100%; max-width: 320px; margin: 0 auto; position: relative; }}
        video {{ width: 100%; height: auto; border-radius: 4px; margin-bottom: 10px; }}
        h2 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
        .sentence-container {{ background-color: #e6f7ff; padding: 15px; border-radius: 8px; 
                             margin-bottom: 30px; border-left: 4px solid #1890ff; width: 100%; }}
        .status {{ text-align: center; padding: 10px; background-color: #fff3cd; color: #856404; 
                 border-radius: 5px; margin: 20px 0; }}
        #auto-refresh-toggle {{ position: fixed; top: 10px; right: 10px; padding: 5px 10px; 
                              background-color: #4CAF50; color: white; border: none; 
                              border-radius: 4px; cursor: pointer; }}
        #timestamp {{ display: none; }}
        .info-text {{ text-align: center; padding: 20px; background-color: white; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
        .source-info {{ padding: 8px 12px; border-radius: 4px; display: inline-block; 
                      font-weight: bold; margin: 5px; }}
        .microphone-blocked {{ background-color: #f44336; color: white; }}
        .microphone-allowed {{ background-color: #4CAF50; color: white; }}
        .restart-note {{ font-size: 0.8em; color: #666; margin-top: 10px; }}
        .controls {{ display: flex; justify-content: center; margin-bottom: 20px; }}
        .example {{ background-color: #e8f4fc; padding: 10px; border-radius: 4px; margin: 10px 0; }}
        .no-video-text {{ font-style: italic; color: #666; font-size: 0.8em; margin-top: 5px; }}
        .video-controls {{ display: flex; justify-content: center; margin-top: 5px; }}
        .video-controls button {{ background: #2196f3; color: white; border: none; padding: 5px 10px; margin: 0 5px; border-radius: 4px; cursor: pointer; }}
        .debug-info {{ font-size: 0.7em; color: #999; margin-top: 5px; overflow-wrap: break-word; word-break: break-all; }}
        .word-0 {{ background-color: #e3f2fd; }}
        .word-1 {{ background-color: #bbdefb; }}
        .word-2 {{ background-color: #90caf9; }}
        .word-3 {{ background-color: #64b5f6; }}
        .word-4 {{ background-color: #42a5f5; }}
        .word-5 {{ background-color: #2196f3; color: white; }}
        .word-6 {{ background-color: #1e88e5; color: white; }}
        .word-7 {{ background-color: #1976d2; color: white; }}
        .word-8 {{ background-color: #1565c0; color: white; }}
        .word-9 {{ background-color: #0d47a1; color: white; }}
        .gmeet-status {{ padding: 8px 12px; border-radius: 4px; display: inline-block; font-weight: bold; margin: 5px; }}
        .gmeet-active {{ background-color: #4CAF50; color: white; }}
        .gmeet-inactive {{ background-color: #f44336; color: white; }}
    </style>
    <script>
        function checkForUpdates() {{
            fetch(window.location.href + '?t=' + new Date().getTime())
                .then(response => response.text())
                .then(html => {{
                    const parser = new DOMParser();
                    const newDoc = parser.parseFromString(html, 'text/html');
                    const newTimestamp = newDoc.getElementById('timestamp');
                    const currentTimestamp = document.getElementById('timestamp');
                    
                    if (newTimestamp && currentTimestamp && newTimestamp.textContent !== currentTimestamp.textContent) {{
                        document.open();
                        document.write(html);
                        document.close();
                    }}
                }});
        }}
        
        function toggleAutoRefresh() {{
            const button = document.getElementById('auto-refresh-toggle');
            if (button.textContent === 'Auto-Refresh: ON') {{
                button.textContent = 'Auto-Refresh: OFF';
                button.style.backgroundColor = '#f44336';
                clearInterval(window.refreshInterval);
            }} else {{
                button.textContent = 'Auto-Refresh: ON';
                button.style.backgroundColor = '#4CAF50';
                window.refreshInterval = setInterval(checkForUpdates, 1000);
            }}
        }}
        
        function playVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.play();
            }}
        }}
        
        function pauseVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.pause();
            }}
        }}
        
        function restartVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.currentTime = 0;
                video.play();
            }}
        }}
        
        window.onload = function() {{
            toggleAutoRefresh();
            
            // Auto-play all videos (important for sign language videos)
            const videos = document.querySelectorAll('video');
            videos.forEach((video, index) => {{
                video.play().catch(error => {{
                    console.log('Auto-play prevented:', error);
                }});
                
                // Also add event listener for when video ends to restart it
                video.addEventListener('ended', function() {{
                    this.currentTime = 0;
                    this.play();
                }});
            }});
        }};
    </script>
</head>
<body>
    <h2>Sign Language Translator</h2>
    <button id="auto-refresh-toggle" onclick="toggleAutoRefresh()">Auto-Refresh: OFF</button>
    
    <div class="controls">
        <div class="source-info microphone-{{"allowed" if self.allow_mic else "blocked"}}">
            Audio Source: {audio_source}
        </div>
        <div class="gmeet-status gmeet-{{"active" if self.gmeet_active else "inactive"}}">
            Google Meet: {gmeet_status}
        </div>
    </div>
    
    <div id="status" class="status">Translating speech from Google Meet participants...</div>
    <div id="timestamp">{time.time()}</div>
    <div id="content">
        <div class="transcription"><strong>Transcription:</strong> Waiting for speech to translate...</div>
        <div class="stack-container">
            <div class="info-text">
                Waiting for speech to translate...
            </div>
        </div>
    </div>
</body>
</html>
'''
        
        # Save HTML file
        with open(self.html_file_path, 'w') as f:
            f.write(html)
        
        # Update the last update time
        self.last_update_time = time.time()
        
        # Open in browser if not already open
        if not self.current_browser_tab:
            self.current_browser_tab = webbrowser.open(f'file://{os.path.abspath(self.html_file_path)}')
            
    def list_audio_devices(self):
        """List all available audio devices."""
        logger.info("\nAvailable Audio Devices:")
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            logger.info(f"Device {i}: {dev['name']}")
            logger.info(f"  Input channels: {dev['max_input_channels']}")
            logger.info(f"  Output channels: {dev['max_output_channels']}")
            logger.info(f"  Default sample rate: {dev['default_samplerate']}")
            logger.info("")
    
    def find_output_device(self):
        """Find an appropriate output device for capturing call audio."""
        devices = sd.query_devices()
        
        # Keywords for output devices like speakers and headphones
        output_device_keywords = ['speaker', 'output', 'headphone', 'hdmi', 'audio', 'playback', 'monitor']
        
        # Keywords specifically for Google Meet or video call output
        gmeet_keywords = ['meet', 'call', 'virtual', 'monitor', 'output', 'system', 'default']
        
        # Keywords that indicate microphone (to avoid completely)
        microphone_keywords = ['mic', 'microphone', 'input', 'webcam', 'camera']
        
        logger.info("\nLooking for output devices to capture Google Meet call audio...")
        if not self.allow_mic:
            logger.info("Microphone input is BLOCKED - only system audio devices will be used")
        
        # Create a scoring system for devices to find the best output device
        device_scores = []
        for i, device in enumerate(devices):
            # Check if the device is valid
            score = 0
            name = device['name'].lower()
            logger.info(f"Checking device {i}: {device['name']}")
            
            # Check if it's a microphone
            is_microphone = False
            for keyword in microphone_keywords:
                if keyword in name:
                    logger.info(f"  Found microphone keyword '{keyword}' in device name")
                    is_microphone = True
                    break
            
            # Skip devices that are microphones if microphones are not allowed
            if is_microphone and not self.allow_mic:
                logger.info(f"  Skipping device {i} as it appears to be a microphone (microphones blocked)")
                continue
            
            # Heavily penalize microphones even if allowed (only use as last resort)
            if is_microphone:
                logger.info(f"  Device is a microphone, applying penalty (-15)")
                score -= 15
            
            # SPECIAL HANDLING: Prioritize monitor sources which are best for capturing system audio
            if 'monitor' in name:
                logger.info(f"  This is a monitor source, ideal for capturing system audio (+15)")
                score += 15
                
            # SPECIAL HANDLING: PulseAudio/PipeWire devices often work well for system audio
            if 'pulse' in name or 'pipewire' in name:
                logger.info(f"  This is a PulseAudio/PipeWire device, good for system audio (+10)")
                score += 10
                
            # Award points for output keywords in the name
            for keyword in output_device_keywords:
                if keyword in name:
                    logger.info(f"  Found keyword '{keyword}' in device name (+2)")
                    score += 2
            
            # Additional points for Google Meet related keywords
            for keyword in gmeet_keywords:
                if keyword in name:
                    logger.info(f"  Found Google Meet related keyword '{keyword}' in device name (+5)")
                    score += 5
            
            # Award points for being the default output device
            if i == sd.default.device[1]:
                logger.info(f"  This is the default output device (+5)")
                score += 5
                
            # Award points for having minimal input channels (typical for pure output devices)
            if device['max_input_channels'] <= 1 and device['max_output_channels'] > 0:
                logger.info(f"  This device has minimal input channels (+3)")
                score += 3
                
            # SPECIAL HANDLING: Check if the device has any input channels at all
            # For system audio capture, we generally need at least 1 input channel
            if device['max_input_channels'] <= 0:
                logger.info(f"  Device has no input channels, may not work for audio capture (-10)")
                score -= 10
            
            # Record the score
            device_scores.append((i, score, device['name']))
        
        # Sort by score in descending order
        device_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Try to find a good monitor source first
        for idx, score, name in device_scores:
            if 'monitor' in name.lower() and score > 0:
                logger.info(f"\nSelected monitor device {idx}: {name} (score: {score})")
                return idx
                
        # Fall back to highest scoring device
        if device_scores:
            best_device_idx, score, name = device_scores[0]
            logger.info(f"\nSelected device {best_device_idx}: {name} (score: {score})")
            return best_device_idx
        
        # Fallback to default output device
        default_output = sd.default.device[1]
        logger.info(f"\nNo suitable output device found, using default: {devices[default_output]['name']}")
        return default_output
    
    def audio_callback(self, indata, frames, time, status):
        """This is called for each audio block from the output device."""
        if status:
            logger.warning(f"Status: {status}")
            
        # Check if Google Meet is active - if not, don't process the audio
        if not self.check_google_meet_active():
            # Occasionally log that we're waiting for Google Meet
            if np.random.random() < 0.01:  # 1% chance to log
                logger.info("Waiting for Google Meet to become active")
            return
        
        # Calculate audio level - used for speech detection
        audio_level = np.abs(indata).mean()
        
        # Debug: Occasionally print the audio level for monitoring
        if np.random.random() < 0.01:  # 1% chance to log level for monitoring
            logger.debug(f"Current audio level: {audio_level:.6f}")
        
        # Skip processing if the audio level is very high (likely user's own voice)
        if audio_level > self.own_voice_threshold:
            if np.random.random() < 0.05:  # 5% chance to log
                logger.info(f"Skipping likely own voice: level={audio_level:.6f}")
            return
        
        # Enhanced spectral characteristics detection specifically for Google Meet speech
        is_speech_like = False
        is_call_audio = False
        
        if len(indata) > 0:
            # Extract first channel if multichannel
            audio_data = indata[:, 0] if indata.ndim > 1 else indata
            
            # Calculate power spectrum
            if len(audio_data) >= 256:  # Ensure we have enough samples
                spectrum = np.abs(np.fft.rfft(audio_data[:256]))
                
                # Enhanced speech detection for call audio
                if len(spectrum) > 45:
                    # Google Meet and video call speech typically has more energy in 300-3000 Hz range
                    speech_energy = np.sum(spectrum[5:45])
                    total_energy = np.sum(spectrum)
                    
                    if total_energy > 0:
                        speech_ratio = speech_energy / total_energy
                        
                        # More lenient threshold for speech detection in call audio
                        is_speech_like = speech_ratio > 0.4  # Was 0.45
                        
                        # Call audio also has specific frequency characteristics
                        # Higher frequencies are often filtered out in call audio
                        high_freq_energy = np.sum(spectrum[45:]) if len(spectrum) > 45 else 0
                        high_freq_ratio = high_freq_energy / total_energy if total_energy > 0 else 0
                        
                        # Call audio typically has less high-frequency energy - more lenient criteria
                        is_call_audio = high_freq_ratio < 0.2 and is_speech_like  # Was 0.15
                        
                        if is_speech_like and np.random.random() < 0.05:  # Log occasionally
                            logger.debug(f"Speech ratio: {speech_ratio:.2f}, High freq ratio: {high_freq_ratio:.2f}")
        
        # Lower threshold specifically for Google Meet/call audio
        # Call audio is typically lower volume than normal audio
        call_audio_threshold = 0.0002  # Very low threshold for call audio (was 0.0003)
        
        # Queue audio if ANY of the following conditions are true:
        # 1. Has speech-like spectral characteristics 
        # 2. OR appears to be call audio
        # 3. OR has sufficient audio level to potentially be speech
        if (is_speech_like or is_call_audio or audio_level > call_audio_threshold):
            # Log detection reasoning occasionally
            if np.random.random() < 0.02:  # 2% chance
                logger.info(f"Capturing audio: level={audio_level:.6f}, speech-like={is_speech_like}, call-audio={is_call_audio}")
            
            self.audio_queue.put(indata.copy())
    
    def start_recording(self):
        """Start recording audio from the output device."""
        self.is_recording = True
        
        # Find the output device
        device_index = self.find_output_device()
        
        # Get device info
        device_info = sd.query_devices(device_index)
        logger.info(f"Using device: {device_info['name']}")
        logger.info(f"  Input channels: {device_info['max_input_channels']}")
        logger.info(f"  Output channels: {device_info['max_output_channels']}")
        logger.info(f"  Default sample rate: {device_info['default_samplerate']}")
        
        # Use different approaches based on the operating system
        try:
            # First approach: Try using system loopback on Linux
            logger.info("Trying to capture system audio using loopback...")
            
            # For Linux systems with PulseAudio/ALSA
            if 'linux' in sys.platform:
                # Check if it's a monitor source already
                is_monitor = 'monitor' in device_info['name'].lower()
                
                try:
                    # If it's already a monitor source, don't add "monitor:"
                    device_string = f"{device_index}" if is_monitor else f"monitor:{device_index}"
                    logger.info(f"Attempting to use device string: {device_string}")
                    
                    self.stream = sd.InputStream(
                        device=device_string,
                        channels=self.channels,
                        samplerate=self.sample_rate,
                        callback=self.audio_callback,
                        blocksize=1024
                    )
                    logger.info("Started recording using PulseAudio monitor source")
                    self.stream.start()
                    
                except Exception as e:
                    logger.error(f"PulseAudio monitor approach failed: {e}")
                    
                    # Try special PulseAudio naming conventions
                    try:
                        # Try finding PulseAudio or PipeWire directly
                        pulse_idx = None
                        for i, dev in enumerate(sd.query_devices()):
                            if any(name in dev['name'].lower() for name in ['pulse', 'pipewire']):
                                pulse_idx = i
                                break
                                
                        if pulse_idx is not None:
                            logger.info(f"Trying PulseAudio/PipeWire device {pulse_idx}")
                            self.stream = sd.InputStream(
                                device=pulse_idx,
                                channels=self.channels,
                                samplerate=self.sample_rate,
                                callback=self.audio_callback,
                                blocksize=1024
                            )
                            logger.info("Started recording using PulseAudio/PipeWire device")
                            self.stream.start()
                        else:
                            raise Exception("No PulseAudio/PipeWire device found")
                    
                    except Exception as e:
                        logger.error(f"PulseAudio special approach failed: {e}")
                        
                        # Fallback to standard device
                        self.stream = sd.InputStream(
                            device=device_index,
                            channels=self.channels,
                            samplerate=self.sample_rate,
                            callback=self.audio_callback,
                            blocksize=1024
                        )
                        logger.info("Started recording using standard device approach")
                        self.stream.start()
            
            # For other operating systems
            else:
                # Standard approach for other platforms
                self.stream = sd.InputStream(
                    device=device_index,
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    callback=self.audio_callback,
                    blocksize=1024
                )
                logger.info("Started recording from output device (standard mode)")
                self.stream.start()
            
        except Exception as e:
            logger.error(f"Error starting stream: {e}")
            logger.info("Trying alternative capture method...")
            
            try:
                # Try using device string with name "default" on Linux
                if 'linux' in sys.platform:
                    self.stream = sd.InputStream(
                        device="default",
                        channels=self.channels,
                        samplerate=self.sample_rate,
                        callback=self.audio_callback,
                        blocksize=1024
                    )
                    logger.info("Started recording using 'default' device")
                    self.stream.start()
                else:
                    # Fallback to direct device index with ":" notation (works on some systems)
                    self.stream = sd.InputStream(
                        device=f":{device_index}",  # Monitor notation in some systems
                        channels=self.channels,
                        samplerate=self.sample_rate,
                        callback=self.audio_callback,
                        blocksize=1024
                    )
                    logger.info("Started recording in monitor mode")
                    self.stream.start()
                
            except Exception as e2:
                logger.error(f"Monitor mode failed: {e2}")
                logger.info("Falling back to default output device...")
                
                # Final fallback - just use the default output device
                self.stream = sd.InputStream(
                    device=sd.default.device[1],
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    callback=self.audio_callback,
                    blocksize=1024
                )
                
                logger.info("Started recording from default output device")
                self.stream.start()
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self.process_audio)
        self.process_thread.start()
    
    def stop_recording(self):
        """Stop recording audio."""
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'process_thread'):
            self.process_thread.join()
        self.video_server.stop()
    
    def save_audio_to_wav(self, audio_data, filename):
        """Save audio data to a WAV file."""
        # Normalize audio data
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 2 bytes per sample
            wf.setframerate(self.sample_rate)
            wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
    
    def display_videos(self, videos_data):
        """Display sign language words in the browser, stacked vertically with last word at top."""
        if not videos_data:
            logger.info("No videos to display")
            return
            
        # Get videos and formatted words from response
        videos = videos_data.get('videos', [])
        formatted_words = videos_data.get('formatted_words', [])
        text = videos_data.get('text', '')
        
        if not videos and not formatted_words:
            logger.info("No videos or words found in response")
            return
        
        logger.info(f"Displaying content with videos for: {text}")
        
        # Group words into sentences
        sentences = self.group_into_sentences(text)

        # Determine audio source display text
        mic_status = "ALLOWED" if self.allow_mic else "BLOCKED"
        audio_source = "System Audio + Microphone" if self.allow_mic else "System Audio ONLY (Google Meet)"
        gmeet_status = "ACTIVE" if self.check_google_meet_active() else "INACTIVE"
        
        # Create HTML content - using f-strings with double braces for CSS
        html = f'''<!DOCTYPE html>
        <html>
        <head>
    <title>Sign Language Translator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f0f0; padding-bottom: 20px; }}
        .transcription {{ background-color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 18px; }}
        .word-container {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                          padding: 20px; margin-bottom: 15px; text-align: center; width: 100%; max-width: 600px; }}
        .stack-container {{ display: flex; flex-direction: column-reverse; align-items: center; width: 100%; }}
        .word {{ font-weight: bold; font-size: 2em; color: #333; padding: 10px; }}
        .video-container {{ width: 100%; max-width: 320px; margin: 0 auto; position: relative; }}
        video {{ width: 100%; height: auto; border-radius: 4px; margin-bottom: 10px; }}
        h2 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
        .sentence-container {{ background-color: #e6f7ff; padding: 15px; border-radius: 8px; 
                             margin-bottom: 30px; border-left: 4px solid #1890ff; width: 100%; }}
        .status {{ text-align: center; padding: 10px; background-color: #fff3cd; color: #856404; 
                 border-radius: 5px; margin: 20px 0; }}
        #auto-refresh-toggle {{ position: fixed; top: 10px; right: 10px; padding: 5px 10px; 
                              background-color: #4CAF50; color: white; border: none; 
                              border-radius: 4px; cursor: pointer; }}
        #timestamp {{ display: none; }}
        .source-info {{ padding: 8px 12px; border-radius: 4px; display: inline-block; 
                       font-weight: bold; margin: 5px; }}
        .microphone-blocked {{ background-color: #f44336; color: white; }}
        .microphone-allowed {{ background-color: #4CAF50; color: white; }}
        .controls {{ display: flex; justify-content: center; margin-bottom: 20px; }}
        .no-video-text {{ font-style: italic; color: #666; font-size: 0.8em; margin-top: 5px; }}
        .word-0 {{ background-color: #e3f2fd; }}
        .word-1 {{ background-color: #bbdefb; }}
        .word-2 {{ background-color: #90caf9; }}
        .word-3 {{ background-color: #64b5f6; }}
        .word-4 {{ background-color: #42a5f5; }}
        .word-5 {{ background-color: #2196f3; color: white; }}
        .word-6 {{ background-color: #1e88e5; color: white; }}
        .word-7 {{ background-color: #1976d2; color: white; }}
        .word-8 {{ background-color: #1565c0; color: white; }}
        .word-9 {{ background-color: #0d47a1; color: white; }}
        .video-controls {{ display: flex; justify-content: center; margin-top: 5px; }}
        .video-controls button {{ background: #2196f3; color: white; border: none; padding: 5px 10px; margin: 0 5px; border-radius: 4px; cursor: pointer; }}
        .debug-info {{ font-size: 0.7em; color: #999; margin-top: 5px; overflow-wrap: break-word; word-break: break-all; }}
        .gmeet-status {{ padding: 8px 12px; border-radius: 4px; display: inline-block; font-weight: bold; margin: 5px; }}
        .gmeet-active {{ background-color: #4CAF50; color: white; }}
        .gmeet-inactive {{ background-color: #f44336; color: white; }}
            </style>
    <script>
        function checkForUpdates() {{
            fetch(window.location.href + '?t=' + new Date().getTime())
                .then(response => response.text())
                .then(html => {{
                    const parser = new DOMParser();
                    const newDoc = parser.parseFromString(html, 'text/html');
                    const newTimestamp = newDoc.getElementById('timestamp');
                    const currentTimestamp = document.getElementById('timestamp');
                    
                    if (newTimestamp && currentTimestamp && newTimestamp.textContent !== currentTimestamp.textContent) {{
                        document.open();
                        document.write(html);
                        document.close();
                    }}
                }});
        }}
        
        function toggleAutoRefresh() {{
            const button = document.getElementById('auto-refresh-toggle');
            if (button.textContent === 'Auto-Refresh: ON') {{
                button.textContent = 'Auto-Refresh: OFF';
                button.style.backgroundColor = '#f44336';
                clearInterval(window.refreshInterval);
            }} else {{
                button.textContent = 'Auto-Refresh: ON';
                button.style.backgroundColor = '#4CAF50';
                window.refreshInterval = setInterval(checkForUpdates, 1000);
            }}
        }}
        
        function playVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.play();
            }}
        }}
        
        function pauseVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.pause();
            }}
        }}
        
        function restartVideo(videoId) {{
            const video = document.getElementById(videoId);
            if (video) {{
                video.currentTime = 0;
                video.play();
            }}
        }}
        
        window.onload = function() {{
            toggleAutoRefresh();
            
            // Auto-play all videos (important for sign language videos)
            const videos = document.querySelectorAll('video');
            videos.forEach((video, index) => {{
                video.play().catch(error => {{
                    console.log('Auto-play prevented:', error);
                }});
                
                // Also add event listener for when video ends to restart it
                video.addEventListener('ended', function() {{
                    this.currentTime = 0;
                    this.play();
                }});
            }});
        }};
    </script>
        </head>
        <body>
    <h2>Sign Language Translator</h2>
    <button id="auto-refresh-toggle" onclick="toggleAutoRefresh()">Auto-Refresh: OFF</button>
    
    <div class="controls">
        <div class="source-info microphone-{{"allowed" if self.allow_mic else "blocked"}}">
            Audio Source: {audio_source}
        </div>
        <div class="gmeet-status gmeet-{{"active" if self.gmeet_active else "inactive"}}">
            Google Meet: {gmeet_status}
        </div>
    </div>
    
    <div id="status" class="status">Translating speech from Google Meet participants...</div>
    <div id="timestamp">{time.time()}</div>
    <div id="content">
        <div class="transcription"><strong>Transcription:</strong> {text}</div>
'''
        
        # Create a stack container for all words
        html += '''
        <div class="stack-container">
'''
        
        # Create a mapping of words to their video paths
        word_to_video = {}
        if formatted_words and videos and len(formatted_words) == len(videos):
            for word, video in zip(formatted_words, videos):
                if video and len(video) > 0:
                    word_to_video[word.lower()] = video
                
        # Filter to only include words that have videos
        valid_videos = []
        valid_words = []
        
        for word, video in zip(formatted_words, videos):
            if video and len(video) > 0:
                valid_videos.append(video)
                valid_words.append(word)
        
        # Reverse the order so the last word is at the top
        for i, (word, video_path) in enumerate(zip(reversed(valid_words), reversed(valid_videos))):
            css_class = f"word-{min(i, 9)}"  # Use up to 10 color classes
            
            html += f'''
        <div class="word-container {css_class}">
            <div class="word">{word}</div>
'''
            
            # Display the video
            if video_path and len(video_path) > 0:
                video_id = f"video_{i}"
                html += f'''
            <div class="video-container">
                <video id="{video_id}" autoplay loop muted playsinline controls>
                    <source src="{video_path}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <div class="video-controls">
                    <button onclick="playVideo('{video_id}')">▶️ Play</button>
                    <button onclick="restartVideo('{video_id}')">🔄 Restart</button>
                </div>
            </div>
'''
            
            html += '''
        </div>
'''
        
        # Complete the stack container
        html += '''
        </div>
'''
        
        # Complete the HTML
        html += '''
    </div>
        </body>
        </html>
'''
        
        # Save HTML file
        with open(self.html_file_path, 'w') as f:
            f.write(html)
        
        # Update the last update time
        self.last_update_time = time.time()
        
        # Open in browser if not already open
        if not self.current_browser_tab:
            self.current_browser_tab = webbrowser.open(f'file://{os.path.abspath(self.html_file_path)}')
            
    def group_into_sentences(self, text):
        """Split text into sentences for better organization."""
        # Simple sentence splitting by punctuation
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def process_audio(self):
        """Process recorded audio and send to backend."""
        buffer = []
        buffer_duration = 2.0  # seconds - even shorter for Google Meet audio to be more responsive
        samples_per_buffer = self.sample_rate * buffer_duration
        
        # Server URL
        server_url = 'http://127.0.0.1:8000/transcribe/'
        
        # Words to filter out (fillers, common noise words)
        filler_words = {'um', 'uh', 'er', 'ah', 'like', 'you know', 'hmm', 'so', 'well', 'actually', 'basically'}
        
        # Ultra-low threshold for consecutive silence detection specifically for Google Meet audio
        silence_threshold = 0.00015  # Extremely low for Google Meet call audio
        consecutive_silence_frames = 0
        max_silence_frames = 5  # Reset buffer after this many silent frames (lower for Google Meet audio)
        
        # Minimum time between processing chunks to avoid overloading the server
        min_processing_interval = 0.8  # seconds (shorter interval for more responsiveness)
        last_processing_time = time.time()
        
        logger.info("Starting audio processing thread - highly optimized for Google Meet calls")
        
        while self.is_recording:
            try:
                try:
                    # Get audio data from queue with a short timeout for fast response
                    audio_data = self.audio_queue.get(timeout=0.1)
                    
                    # Calculate audio level
                    audio_level = np.abs(audio_data).mean()
                    
                    # Check if this is silence (using ultra-low threshold for call audio)
                    if audio_level < silence_threshold:
                        consecutive_silence_frames += 1
                        
                        current_time = time.time()
                        time_since_last_process = current_time - last_processing_time
                        
                        # If we've had enough consecutive silent frames and it's been long
                        # enough since our last processing, process the buffer and reset
                        if consecutive_silence_frames >= max_silence_frames and buffer and time_since_last_process >= min_processing_interval:
                            logger.info(f"Processing buffer after silence detection ({consecutive_silence_frames} frames)")
                            full_buffer = np.concatenate(buffer)
                            self.process_audio_buffer(full_buffer, server_url, filler_words)
                            buffer = []
                            consecutive_silence_frames = 0
                            last_processing_time = current_time
                    else:
                        # Reset consecutive silence counter if we detect non-silence
                        consecutive_silence_frames = 0
                        buffer.append(audio_data)
                        
                except queue.Empty:
                    continue
                
                # If we have enough data and it's been at least min_processing_interval
                # since last processing, process the buffer
                current_time = time.time()
                time_since_last_process = current_time - last_processing_time
                
                if buffer and len(buffer) * len(buffer[0]) >= samples_per_buffer and time_since_last_process >= min_processing_interval:
                    full_buffer = np.concatenate(buffer)
                    
                    # Check if the audio is not completely silent
                    audio_level = np.abs(full_buffer).mean()
                    logger.info(f"Audio level: {audio_level:.6f}")
                    
                    # Use an extremely low threshold specifically for Google Meet audio detection
                    gmeet_audio_threshold = 0.00015  # Ultra-low threshold specifically for Google Meet
                    
                    if audio_level > gmeet_audio_threshold:
                        self.process_audio_buffer(full_buffer, server_url, filler_words)
                        last_processing_time = current_time
                    else:
                        logger.info("Audio is too quiet, skipping processing")
                    
                    # Clear buffer after processing
                    buffer = []
                
            except Exception as e:
                logger.error(f"Error in process_audio: {e}")
                time.sleep(1)  # Avoid tight loop in case of repeated errors
                
    def process_audio_buffer(self, audio_buffer, server_url, filler_words):
        """Process a filled audio buffer and send to server."""
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            self.save_audio_to_wav(audio_buffer, temp_file.name)
            logger.info(f"\nProcessing audio chunk of size: {len(audio_buffer)} samples")
            
            # Send to backend
            try:
                with open(temp_file.name, 'rb') as audio_file:
                    files = {'audio': ('audio.wav', audio_file, 'audio/wav')}
                    logger.info(f"Sending audio to backend at {server_url}...")
                    
                    # First check if server is reachable
                    try:
                        requests.get('http://127.0.0.1:8000/', timeout=2)
                    except requests.exceptions.ConnectionError:
                        logger.error("Could not connect to Django server. Please make sure it's running with 'python3 manage.py runserver'")
                        return
                    
                    # Send as multipart form data
                    response = requests.post(
                        server_url,
                        files=files,
                        timeout=30  # Add timeout
                    )
                    
                    if response.ok:
                        result = response.json()
                        if 'error' in result:
                            logger.error(f"Error from server: {result['error']}")
                        else:
                            transcription = result.get('text', '')
                            logger.info("\nTranscription: " + transcription)
                            
                            # Log the full result for debugging
                            logger.info(f"Server response: {result}")
                            
                            # Even if transcription is empty, check audio level
                            audio_level = np.abs(audio_buffer).mean()
                            
                            # For Google Meet audio, we want to be more sensitive
                            if not transcription or transcription.strip() == '':
                                # If audio level is significant but no transcription, 
                                # try to interpret it as possible speech
                                if audio_level > 0.3:  # A moderate threshold
                                    logger.warning("Empty transcription received but audio level significant. Using placeholder.")
                                    # Use placeholder for non-empty but unrecognized speech
                                    transcription = "[Speech detected]"
                                    result['text'] = transcription
                                    result['formatted_words'] = ["Speech"]
                                    
                                    # Ensure we have a video for 'Speech'
                                    # Try to use a generic placeholder video or create one if needed
                                    speech_video_path = '/static/Speech.mp4'
                                    
                                    # Check if we have speech video in static folder
                                    if not os.path.exists(os.path.join('static', 'Speech.mp4')):
                                        # Since there's no video, just ensure we have the minimal JSON structure
                                        logger.warning("No speech placeholder video found - using text only")
                                    
                                    # Create or update videos list
                                    if 'videos' not in result or not result['videos']:
                                        result['videos'] = [speech_video_path]
                                else:
                                    logger.warning("Empty transcription received. Audio might be too quiet or unclear.")
                                    return
                            
                            # Filter out filler words and normalize text
                            processed_transcription = self.filter_text(transcription, filler_words)
                            if processed_transcription != transcription:
                                logger.info(f"Filtered transcription: {processed_transcription}")
                                # Update the transcription in the result
                                result['text'] = processed_transcription
                                
                                # Also update the formatted_words list to match the filtered text
                                filtered_words = processed_transcription.split()
                                result['formatted_words'] = [word.capitalize() for word in filtered_words]
                                
                                # We need to ensure the videos list matches the new word count
                                if 'videos' in result and len(result['videos']) != len(filtered_words):
                                    # If we have videos but in the wrong count, try to match them up
                                    # by preserving the videos we have for words that remain
                                    original_words = transcription.split()
                                    original_videos = result.get('videos', [])
                                    
                                    # Create a word-to-video mapping from the original
                                    word_to_video = {}
                                    if len(original_words) == len(original_videos):
                                        for i, word in enumerate(original_words):
                                            word_to_video[word.lower()] = original_videos[i]
                                    
                                    # Create a new videos list for the filtered words
                                    new_videos = []
                                    for word in filtered_words:
                                        if word.lower() in word_to_video:
                                            new_videos.append(word_to_video[word.lower()])
                                        else:
                                            # No video for this word, use a placeholder path
                                            new_videos.append('')
                                    
                                    # Update the videos list
                                    result['videos'] = new_videos
                            
                            # Check if videos are present and make sure all paths are valid
                            if 'videos' in result:
                                videos = result['videos']
                                
                                # Ensure all video paths are properly formatted with leading slash if needed
                                for i, video_path in enumerate(videos):
                                    if video_path and not video_path.startswith('/') and not video_path.startswith('http'):
                                        videos[i] = '/' + video_path
                                        
                                result['videos'] = videos
                                
                                # Make the absolute URLs for videos
                                base_url = "http://127.0.0.1:8000"
                                for i, video_path in enumerate(videos):
                                    if video_path and video_path.startswith('/static/'):
                                        # Convert to full URL for proper video display
                                        videos[i] = f"{base_url}{video_path}"
                                
                                # Update videos in result
                                result['videos'] = videos
                                
                                # Log a summary
                                video_count = sum(1 for v in videos if v and len(v) > 0)
                                logger.info(f"Found {video_count} valid videos out of {len(videos)} words")
                                
                                # FILTER MODIFICATION: Only show words that have videos
                                # Filter words and videos to only include words with videos
                                if 'formatted_words' in result:
                                    valid_videos = []
                                    valid_words = []
                                    
                                    for word, video in zip(result['formatted_words'], videos):
                                        if video and len(video) > 0:
                                            valid_videos.append(video)
                                            valid_words.append(word)
                                    
                                    # If we found valid words with videos
                                    if valid_words:
                                        # Create a new transcription with only the words that have videos
                                        result['text'] = ' '.join(valid_words)
                                        result['formatted_words'] = valid_words
                                        result['videos'] = valid_videos
                                        logger.info(f"Filtered to only words with videos: {result['text']}")
                                
                            # Display videos if available
                            if 'videos' in result or 'formatted_words' in result:
                                logger.info(f"\nDisplaying sign language content...")
                                self.display_videos(result)
                            else:
                                logger.warning("No videos or words returned from server")
                    else:
                        logger.error(f"Error: {response.status_code} - {response.text}")
            except requests.exceptions.Timeout:
                logger.error("Error: Request timed out. The server took too long to respond.")
            except requests.exceptions.ConnectionError:
                logger.error("Error: Could not connect to the server. Is the Django server running?")
            except Exception as e:
                logger.error(f"Error sending audio to backend: {e}")
            finally:
                # Clean up temporary file
                try:
                    os.remove(temp_file.name)
                except Exception as e:
                    logger.error(f"Error removing temporary file: {e}")
                    
    def filter_text(self, text, filler_words):
        """Filter out filler words and normalize text."""
        # Split into words
        words = text.split()
        
        # Filter out filler words
        filtered_words = [word for word in words if word.lower() not in filler_words]
        
        # Remove extra spaces and join back
        filtered_text = ' '.join(filtered_words)
        
        return filtered_text

def main():
    try:
        # Command line arguments for better testing
        parser = argparse.ArgumentParser(description='Audio Speech To Sign Language Converter')
        parser.add_argument('--debug', action='store_true', help='Run in debug mode without requiring Django backend')
        parser.add_argument('--device', type=int, help='Specify audio device index to use')
        parser.add_argument('--gmeet', action='store_true', help='Optimize for Google Meet audio capture (default: True)', default=True)
        parser.add_argument('--allow-mic', action='store_true', help='Allow microphone input (default: False)', default=False)
        args = parser.parse_args()
        
        # Create audio capture instance
        audio_capture = AudioCapture(allow_mic=args.allow_mic)
        
        # List available audio devices
        audio_capture.list_audio_devices()
        
        # Print configuration details
        logger.info("\n=== Audio Speech To Sign Language Converter ===")
        logger.info("Mode: Google Meet Audio Capture")
        logger.info(f"- Microphone input: {'ALLOWED' if args.allow_mic else 'BLOCKED'}")
        logger.info("- Video display format: Stack (newest at bottom)")
        logger.info("- Audio source: Google Meet participant output")
        logger.info("==============================================\n")
        
        # If in debug mode, add a debug audio callback
        if args.debug:
            logger.info("\nRunning in DEBUG mode - will print audio levels without requiring Django backend")
            
            # Replace the process_audio_buffer method with a debug version
            def debug_process_audio_buffer(self, audio_buffer, server_url, filler_words):
                audio_level = np.abs(audio_buffer).mean()
                logger.info(f"DEBUG: Captured audio chunk with level: {audio_level:.6f}")
                
                # FFT analysis for speech detection
                if len(audio_buffer) > 1024:
                    audio_data = audio_buffer[:1024, 0] if audio_buffer.ndim > 1 else audio_buffer[:1024]
                    spectrum = np.abs(np.fft.rfft(audio_data))
                    if len(spectrum) > 45:
                        speech_energy = np.sum(spectrum[5:45])
                        total_energy = np.sum(spectrum)
                        if total_energy > 0:
                            speech_ratio = speech_energy / total_energy
                            logger.info(f"DEBUG: Speech-like ratio: {speech_ratio:.2f} ({speech_ratio > 0.5})")
                
                # Save a sample to temp file for manual inspection if needed
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    audio_capture.save_audio_to_wav(audio_buffer, temp_file.name)
                    logger.info(f"DEBUG: Saved audio sample to {temp_file.name}")
            
            # Replace the method in the instance
            import types
            audio_capture.process_audio_buffer = types.MethodType(debug_process_audio_buffer, audio_capture)
        
        # If specific device was requested, use it
        if args.device is not None:
            # Create a custom device finder that returns the specified device
            def custom_find_output_device(self):
                devices = sd.query_devices()
                if 0 <= args.device < len(devices):
                    logger.info(f"\nUsing specified device {args.device}: {devices[args.device]['name']}")
                    return args.device
                else:
                    logger.error(f"Invalid device index: {args.device}. Using default method.")
                    # Fall back to original method
                    return AudioCapture.find_output_device(self)
            
            # Replace the method in the instance
            import types
            audio_capture.find_output_device = types.MethodType(custom_find_output_device, audio_capture)
        
        logger.info("\nStarting audio capture from Google Meet participants...")
        logger.info("Press Ctrl+C to stop recording")
        audio_capture.start_recording()
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nStopping audio capture...")
        audio_capture.stop_recording()
        logger.info("Audio capture stopped.")
    except Exception as e:
        logger.error(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 