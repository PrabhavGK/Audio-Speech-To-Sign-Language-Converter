import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sign_videos(text, base_dir):
    """
    Get sign language videos for the given text from the static folder.
    
    Args:
        text (str): The text to find videos for
        base_dir (str): The base directory of the project
        
    Returns:
        list: List of video URLs
    """
    try:
        # Split text into words
        words = text.split()
        
        # For each word, find a corresponding video
        videos = []
        for word in words:
            # Clean the word (remove punctuation, etc.)
            cleaned_word = ''.join(c for c in word if c.isalnum())
            if not cleaned_word:
                continue
            
            # Format word with first letter capitalized
            titled_word = cleaned_word.capitalize()
            
            # Look for a video file in the static folder
            static_path = os.path.join(base_dir, 'static', f"{titled_word}.mp4")
            if os.path.exists(static_path):
                videos.append(f"/static/{titled_word}.mp4")
                logger.info(f"Found video for word: {titled_word}")
            else:
                # If not found with title case, try uppercase (for compatibility)
                upper_word = cleaned_word.upper()
                static_path = os.path.join(base_dir, 'static', f"{upper_word}.mp4")
                if os.path.exists(static_path):
                    videos.append(f"/static/{upper_word}.mp4")
                    logger.info(f"Found video for word (uppercase): {upper_word}")
                else:
                    logger.warning(f"No video found for word: {titled_word}")
        
        return videos
        
    except Exception as e:
        logger.error(f"Error getting sign videos: {str(e)}")
        return []

def create_video_response(text):
    """
    Create a response with both transcription and sign language videos.
    """
    try:
        # Get sign language videos for the text
        videos = get_sign_videos(text, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        return {
            'text': text,
            'videos': videos
        }
        
    except Exception as e:
        logger.error(f"Error creating video response: {str(e)}")
        return {
            'text': text,
            'videos': []
        } 