from django.urls import path
from .views import get_user_chat_history, login_signup, chat, get_chat

urlpatterns = [
    path('login/', login_signup, name='login'),
    path('chat/', chat, name='chat'),
    path('chat-history/<str:user_id>/', get_user_chat_history, name='get_user_chat_history'),
    path('chat/<str:chat_id>/', get_chat, name='get_chat'),
]
