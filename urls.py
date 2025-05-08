from django.urls import path
from . import views, transcribe

urlpatterns = [
    path('', views.index, name='index'),
    path('animation/', views.animation, name='animation'),
    path('transcribe/', transcribe.transcribe_audio, name='transcribe'),
] 