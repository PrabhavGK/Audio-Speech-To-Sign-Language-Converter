import os
import tempfile
import whisper
import torch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize model as None
model = None

def get_model():
    """Lazily load the Whisper model when needed."""
    global model
    if model is None:
        try:
            logger.info("Loading Whisper model...")
            model = whisper.load_model("base", device="cpu", in_memory=True)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {str(e)}", exc_info=True)
            raise
    return model

def transcribe_audio(audio_path):
    """
    Transcribe audio from a file path using Whisper.
    
    Args:
        audio_path (str): Path to the audio file to transcribe
        
    Returns:
        str: Transcribed text
    """
    try:
        # Verify the file exists and has content
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found at {audio_path}")
        
        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            raise ValueError("Audio file is empty")
        
        logger.info(f"Processing audio file of size: {file_size} bytes")
        
        # Get the model (will load if not already loaded)
        model = get_model()
        
        # Transcribe the audio with explicit FP32
        logger.info("Starting transcription...")
        result = model.transcribe(
            audio_path,
            fp16=False,  # Force FP32
            language="en"  # Specify English language
        )
        logger.info("Transcription completed")
        
        # Get the transcribed text
        text = result['text'].strip()
        logger.info(f"Transcribed text: {text}")
        
        return text
        
    except Exception as e:
        logger.error(f"Error during transcription: {str(e)}", exc_info=True)
        raise 