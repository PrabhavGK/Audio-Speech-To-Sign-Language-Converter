from django.http import HttpResponse
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
	
	# Convert word to uppercase
	word = word.upper()
	logger.info(f"Processing word: {word}")
	
	# First try the complete word in assets folder
	word_path = os.path.join('assets', f'{word}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking assets path: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in assets: {word}")
		videos.append(word)
		return videos, missing
	
	# If not in assets, try in static folder
	word_path = os.path.join('static', f'{word}.mp4')
	full_path = os.path.join(settings.BASE_DIR, word_path)
	logger.info(f"Checking static path: {full_path}")
	
	if os.path.exists(full_path):
		logger.info(f"Found complete word in static: {word}")
		videos.append(word)
		return videos, missing
	
	# If word video doesn't exist in either location, try individual letters
	logger.info(f"Breaking down word into letters: {word}")
	for c in word:
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
			with open(temp_path, 'wb+') as destination:
				for chunk in audio_file.chunks():
					destination.write(chunk)
		except Exception as e:
			logger.error(f"Error saving audio file: {str(e)}")
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
			return render(request, 'animation.html', {
				'error': 'No sign language animations found for the recognized words.',
				'text': text,
				'missing_videos': missing_videos
			})

		if missing_videos:
			logger.warning(f"Missing videos for words/letters: {missing_videos}")

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
