from django.urls import path
from .views import login_signup, chat, get_chat_history

urlpatterns = [
    path('login/', login_signup, name='login'),
    path('chat/', chat, name='chat'),
    path('chat-history/<str:chat_id>/', get_chat_history, name='get_chat_history'),
]
