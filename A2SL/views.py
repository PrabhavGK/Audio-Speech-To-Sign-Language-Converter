from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login,logout
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import nltk
from django.contrib.staticfiles import finders
from django.contrib.auth.decorators import login_required
import speech_recognition as sr
import os
from django.conf import settings
import socket
import logging
import requests
from urllib.parse import urlparse
import time
import json
from django.views.decorators.csrf import csrf_exempt
from .transcribe import transcribe_audio
from .sign_language import get_sign_videos

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_internet_connection():
	"""Check internet connectivity and DNS resolution"""
	try:
		# Try to connect to Google's DNS server
		socket.create_connection(("8.8.8.8", 53), timeout=3)
		return True
	except Exception as e:
		logger.error(f"Internet connection check failed: {str(e)}")
		return False

def check_google_speech_service():
	"""Check if Google's speech recognition service is accessible"""
	try:
		response = requests.get("https://speech.googleapis.com", timeout=3)
		return response.status_code != 404  # Service might return different status codes
	except Exception as e:
		logger.error(f"Google speech service check failed: {str(e)}")
		return False

def home_view(request):
	return render(request,'home.html')


def about_view(request):
	return render(request,'about.html')


def contact_view(request):
	return render(request,'contact.html')

def get_word_videos(word):
	"""Get video paths for a word or its individual letters"""
	videos = []
	missing = []
	
	# First try with first letter capital and rest small
	word_title = word.title()
	logger.info(f"Processing word with title case: {word_title}")
	
	# Try the complete word in assets folder with title case
	word_path = os.path.join('assets', f'{word_title}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking assets path with title case: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in assets with title case: {word_title}")
		videos.append(word_title)
		return videos, missing
	
	# If not in assets, try in static folder with title case
	word_path = os.path.join('static', f'{word_title}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking static path with title case: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in static with title case: {word_title}")
		videos.append(word_title)
		return videos, missing
	
	# If title case doesn't work, try all caps
	word_upper = word.upper()
	logger.info(f"Trying with all caps: {word_upper}")
	
	# Try the complete word in assets folder with all caps
	word_path = os.path.join('assets', f'{word_upper}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking assets path with all caps: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in assets with all caps: {word_upper}")
		videos.append(word_upper)
		return videos, missing
	
	# If not in assets, try in static folder with all caps
	word_path = os.path.join('static', f'{word_upper}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking static path with all caps: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in static with all caps: {word_upper}")
		videos.append(word_upper)
		return videos, missing
	
	# If word video doesn't exist in either location, try individual letters
	logger.info(f"Breaking down word into letters: {word_upper}")
	for c in word_upper:
		# First try letter in assets folder
		letter_path = os.path.join('assets', f'{c}.mp4')
		full_path = os.path.join(settings.BASE_DIR, letter_path)
		logger.info(f"Checking letter in assets: {full_path}")
		
		if os.path.exists(full_path):
			logger.info(f"Found letter in assets: {c}")
			videos.append(c)
		else:
			# Try letter in static folder
			letter_path = os.path.join('static', f'{c}.mp4')
			full_path = os.path.join(settings.BASE_DIR, letter_path)
			logger.info(f"Checking letter in static: {full_path}")
			
			if os.path.exists(full_path):
				logger.info(f"Found letter in static: {c}")
				videos.append(c)
			else:
				logger.warning(f"Missing video for letter: {c}")
				missing.append(c)
	
	return videos, missing

@login_required(login_url="login")
def animation_view(request):
	if request.method == 'POST':
		# Check if this is an API request from the extension
		if request.headers.get('Content-Type') == 'application/json':
			try:
				data = json.loads(request.body)
				text = data.get('text', '').upper()
			except json.JSONDecodeError:
				return JsonResponse({'error': 'Invalid JSON'}, status=400)
		else:
			# Handle regular form submission
			audio_file = request.FILES.get('audio')
			if not audio_file:
				return render(request, 'animation.html', {'error': 'Please upload an audio file'})
			
			# Validate audio file
			if not audio_file.name.lower().endswith(('.wav', '.mp3', '.ogg', '.m4a', '.webm')):
				return render(request, 'animation.html', {
					'error': 'Unsupported audio format. Please upload a WAV, MP3, OGG, M4A, or WebM file.'
				})
			
			# Save the uploaded file temporarily
			temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_audio.wav')
			try:
				logger.info(f"Attempting to save audio file to: {temp_path}")
				# Ensure the media directory exists
				os.makedirs(os.path.dirname(temp_path), exist_ok=True)
				
				with open(temp_path, 'wb+') as destination:
					for chunk in audio_file.chunks():
						destination.write(chunk)
				logger.info("Successfully saved audio file")
			except PermissionError as e:
				logger.error(f"Permission error saving audio file: {str(e)}")
				return render(request, 'animation.html', {
					'error': 'Permission denied while saving audio file. Please check directory permissions.'
				})
			except IOError as e:
				logger.error(f"IO error saving audio file: {str(e)}")
				return render(request, 'animation.html', {
					'error': 'Error saving audio file. Please try again.'
				})
			except Exception as e:
				logger.error(f"Unexpected error saving audio file: {str(e)}")
				return render(request, 'animation.html', {
					'error': 'Error saving audio file. Please try again.'
				})
			
			# Initialize speech recognizer
			recognizer = sr.Recognizer()
			
			try:
				# Check internet connectivity
				if not check_internet_connection():
					return render(request, 'animation.html', {
						'error': 'No internet connection. Please check your network connection and try again.'
					})
				
				# Convert audio to text with retries
				max_retries = 3
				retry_delay = 2  # seconds
				
				for attempt in range(max_retries):
					try:
						with sr.AudioFile(temp_path) as source:
							# Adjust for ambient noise
							recognizer.adjust_for_ambient_noise(source)
							audio_data = recognizer.record(source)
							
							# Try Google Speech Recognition
							text = recognizer.recognize_google(audio_data)
							logger.info(f"Successfully recognized text: {text}")
							break
					except sr.UnknownValueError:
						logger.warning("Speech recognition failed: Could not understand audio")
						if attempt == max_retries - 1:
							return render(request, 'animation.html', {
								'error': 'Could not understand the audio. Please speak clearly and try again.'
							})
					except sr.RequestError as e:
						error_message = str(e)
						logger.error(f"Speech recognition request failed (attempt {attempt + 1}/{max_retries}): {error_message}")
						if attempt == max_retries - 1:
							return render(request, 'animation.html', {
								'error': 'Unable to connect to speech recognition service. Please try again later.'
							})
						time.sleep(retry_delay)
					except Exception as e:
						logger.error(f"Unexpected error during speech recognition: {str(e)}")
						if attempt == max_retries - 1:
							return render(request, 'animation.html', {
								'error': f'Error processing audio: {str(e)}'
							})
						time.sleep(retry_delay)
			except Exception as e:
				logger.error(f"Unexpected error during speech recognition: {str(e)}")
				return render(request, 'animation.html', {
					'error': f'Error processing audio: {str(e)}'
				})
			finally:
				# Clean up temporary file
				try:
					if os.path.exists(temp_path):
						os.remove(temp_path)
				except Exception as e:
					logger.error(f"Error removing temporary file: {str(e)}")
			
			if not text:
				return render(request, 'animation.html', {
					'error': 'Could not recognize speech from audio'
				})
		
		# Process the text
		text = text.upper()  # Convert to uppercase
		words = word_tokenize(text)
		logger.info(f"Tokenized words: {words}")

		# Process each word and get its videos
		processed_words = []
		missing_videos = []
		word_video_mapping = {}  # To keep track of which videos correspond to which words
		
		for word in words:
			videos, missing = get_word_videos(word)
			if videos:
				processed_words.extend(videos)
				word_video_mapping[word] = videos
			if missing:
				missing_videos.extend(missing)

		if not processed_words:
			if request.headers.get('Content-Type') == 'application/json':
				return JsonResponse({
					'error': 'No sign language animations found for the recognized words.',
					'text': text,
					'missing_videos': missing_videos
				})
			return render(request, 'animation.html', {
				'error': 'No sign language animations found for the recognized words.',
				'text': text,
				'missing_videos': missing_videos
			})

		if missing_videos:
			logger.warning(f"Missing videos for words/letters: {missing_videos}")

		if request.headers.get('Content-Type') == 'application/json':
			return JsonResponse({
				'words': processed_words,
				'text': text,
				'word_video_mapping': word_video_mapping,
				'missing_videos': missing_videos if missing_videos else None
			})
		
		return render(request, 'animation.html', {
			'words': processed_words,
			'text': text,
			'word_video_mapping': word_video_mapping,
			'missing_videos': missing_videos if missing_videos else None
		})
	else:
		return render(request, 'animation.html')




def signup_view(request):
	if request.method == 'POST':
		form = UserCreationForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request,user)
			# log the user in
			return redirect('animation')
	else:
		form = UserCreationForm()
	return render(request,'signup.html',{'form':form})



def login_view(request):
	if request.method == 'POST':
		form = AuthenticationForm(data=request.POST)
		if form.is_valid():
			#log in user
			user = form.get_user()
			login(request,user)
			if 'next' in request.POST:
				return redirect(request.POST.get('next'))
			else:
				return redirect('animation')
	else:
		form = AuthenticationForm()
	return render(request,'login.html',{'form':form})


def logout_view(request):
	logout(request)
	return redirect("home")

def home(request):
	return render(request, 'A2SL/home.html')

@csrf_exempt
def transcribe(request):
	if request.method == 'POST':
		try:
			# Check if this is a JSON request (for start/stop actions)
			content_type = request.headers.get('Content-Type', '')
			if 'application/json' in content_type:
				try:
					data = json.loads(request.body.decode('utf-8'))
					action = data.get('action')
					
					if action == 'start':
						# Start the audio capture process
						return JsonResponse({'status': 'started'})
					elif action == 'stop':
						# Stop the audio capture process
						return JsonResponse({'status': 'stopped'})
					else:
						return JsonResponse({'error': 'Invalid action'}, status=400)
				except UnicodeDecodeError:
					# Treat as binary audio data
					logger.info("Received binary data with JSON content type")
					
			# Handle audio file upload or binary data
			if 'audio' in request.FILES:
				# Normal file upload
				audio_file = request.FILES['audio']
				temp_path = None
				
				try:
					# Save the uploaded file temporarily
					temp_path = os.path.join(settings.MEDIA_ROOT, f'temp_{audio_file.name}')
					logger.info(f"Saving audio file to: {temp_path}")
					os.makedirs(os.path.dirname(temp_path), exist_ok=True)
					
					with open(temp_path, 'wb+') as destination:
						for chunk in audio_file.chunks():
							destination.write(chunk)
					logger.info("Successfully saved audio file")
					
					# Process the audio file
					return process_audio_file(temp_path)
					
				except Exception as e:
					logger.error(f"Error processing audio: {str(e)}", exc_info=True)
					return JsonResponse({'error': str(e)}, status=500)
					
				finally:
					# Clean up the temporary file
					if temp_path and os.path.exists(temp_path):
						try:
							os.remove(temp_path)
							logger.info("Cleaned up temporary file")
						except Exception as e:
							logger.error(f"Error removing temporary file: {e}")
			else:
				# Binary data in request body
				try:
					# Save the binary data to a temporary file
					temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_audio.wav')
					logger.info(f"Saving binary audio data to: {temp_path}")
					os.makedirs(os.path.dirname(temp_path), exist_ok=True)
					
					with open(temp_path, 'wb') as destination:
						destination.write(request.body)
					logger.info("Successfully saved binary audio data")
					
					# Process the audio file
					return process_audio_file(temp_path)
					
				except Exception as e:
					logger.error(f"Error processing binary audio data: {str(e)}", exc_info=True)
					return JsonResponse({'error': str(e)}, status=500)
					
				finally:
					# Clean up the temporary file
					if temp_path and os.path.exists(temp_path):
						try:
							os.remove(temp_path)
							logger.info("Cleaned up temporary file")
						except Exception as e:
							logger.error(f"Error removing temporary file: {e}")
				
		except Exception as e:
			logger.error(f"Error in POST /transcribe/: {str(e)}", exc_info=True)
			return JsonResponse({'error': str(e)}, status=500)
			
	return JsonResponse({'error': 'Method not allowed'}, status=405)

def process_audio_file(temp_path):
	"""Process an audio file and return transcription and videos"""
	try:
		# Transcribe the audio
		logger.info("Starting audio transcription")
		transcription = transcribe_audio(temp_path)
		logger.info(f"Transcription result: {transcription}")
		
		# Modify transcription to capitalize each word
		formatted_words = [word.capitalize() for word in transcription.split()]
		transcription = ' '.join(formatted_words)
		
		# Get sign language videos for the transcribed text
		logger.info("Getting sign language videos")
		videos = get_sign_videos(transcription, settings.BASE_DIR)
		logger.info(f"Found {len(videos)} videos")
		
		return JsonResponse({
			'text': transcription,
			'videos': videos,
			'formatted_words': formatted_words
		})
	except Exception as e:
		logger.error(f"Error processing audio: {str(e)}", exc_info=True)
		return JsonResponse({'error': str(e)}, status=500)
