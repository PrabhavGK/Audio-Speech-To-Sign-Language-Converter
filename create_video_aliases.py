#!/usr/bin/env python3
import os
import shutil
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_video_aliases():
    """Create aliases (copies) for commonly missing sign language videos."""
    # Directory containing sign language videos
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    
    # Create a list of aliases: (source_video, new_name)
    aliases = [
        # Love - Use "Happy" as a close approximation
        ('Happy.mp4', 'Love.mp4'),
        
        # Common verbs
        ('Walk.mp4', 'Going.mp4'),
        ('Walk.mp4', 'Go.mp4'),
        ('Talk.mp4', 'Say.mp4'),
        ('Talk.mp4', 'Speak.mp4'),
        ('Talk.mp4', 'Said.mp4'),
        ('Sound.mp4', 'Hear.mp4'),
        ('See.mp4', 'Look.mp4'),
        ('See.mp4', 'Watch.mp4'),
        ('Keep.mp4', 'Have.mp4'),
        ('Keep.mp4', 'Has.mp4'),
        ('Learn.mp4', 'Know.mp4'),
        ('I.mp4', 'Im.mp4'),  # I'm
        ('Stay.mp4', 'Live.mp4'),
        ('Stay.mp4', 'Stayed.mp4'),
        ('Stay.mp4', 'Living.mp4'),
        
        # To be verbs
        ('Be.mp4', 'Am.mp4'),
        ('Be.mp4', 'Is.mp4'),
        ('Be.mp4', 'Are.mp4'),
        ('Be.mp4', 'Was.mp4'),
        ('Be.mp4', 'Were.mp4'),
        
        # Negations
        ('Not.mp4', 'Dont.mp4'),  # Don't
        ('Not.mp4', 'Doesnt.mp4'),  # Doesn't
        ('Not.mp4', 'Didnt.mp4'),  # Didn't
        ('Not.mp4', 'No.mp4'),
        
        # Common words
        ('A.mp4', 'An.mp4'),
        ('Great.mp4', 'Awesome.mp4'),
        ('Our.mp4', 'Their.mp4'),
        ('More.mp4', 'Most.mp4'),
        ('Good.mp4', 'Better.mp4'),
        ('Good.mp4', 'Best.mp4'),
        ('Bad.mp4', 'Worse.mp4'),
        ('Bad.mp4', 'Worst.mp4'),
        ('Words.mp4', 'Word.mp4'),
        ('Words.mp4', 'Posture.mp4'),
        ('Words.mp4', 'Die.mp4'),
        ('Words.mp4', 'Driver.mp4'),
        ('Words.mp4', 'Check.mp4'),
        ('Words.mp4', 'For.mp4'),
        ('Words.mp4', 'Every.mp4'),
        ('Words.mp4', 'Single.mp4'),
        ('Words.mp4', 'Waiting.mp4'),
        ('Words.mp4', 'Its.mp4'),
        ('Words.mp4', 'Gonna.mp4'),
    ]
    
    # Check if source files exist first
    source_files = {src for src, _ in aliases}
    existing_sources = []
    
    for source in source_files:
        source_path = os.path.join(static_dir, source)
        if os.path.exists(source_path):
            existing_sources.append(source)
        else:
            logger.warning(f"Source file not found: {source}")
    
    # Create copies for the existing sources
    created_count = 0
    for source, alias in aliases:
        if source in existing_sources:
            source_path = os.path.join(static_dir, source)
            alias_path = os.path.join(static_dir, alias)
            
            # Skip if alias already exists
            if os.path.exists(alias_path):
                logger.info(f"Alias already exists: {alias}")
                continue
                
            try:
                # Create a copy (not symlink for better compatibility)
                shutil.copy2(source_path, alias_path)
                logger.info(f"Created alias: {alias} (from {source})")
                created_count += 1
            except Exception as e:
                logger.error(f"Error creating alias {alias}: {e}")
    
    logger.info(f"Created {created_count} video aliases.")

if __name__ == "__main__":
    create_video_aliases() 