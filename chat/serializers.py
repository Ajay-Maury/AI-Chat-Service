from rest_framework import serializers
from .models import User, Message

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'is_active', 'first_name', 'last_name']

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['chat_id', 'user_id', 'chat_label', 'messages', 'summary', 'is_active', 'created_at', 'updated_at']
