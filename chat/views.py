import json
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from .models import User, Message
from .serializers import UserSerializer, MessageSerializer
from .services import get_or_update_user, fetch_chat, get_openai_response
from django.shortcuts import get_object_or_404


@api_view(['POST'])
def login_signup(request):
    email = request.data.get('email')
    password = request.data.get('password')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')

    user, is_new = get_or_update_user(email, password, first_name, last_name)
    serializer = UserSerializer(user)
    if is_new:
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def get_user(request):
    # Extract email from the request
    email = request.data.get('email')   
    print('\n email:-------', email)

    # Check if email is provided
    if not email:
        return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Fetch the user by email or return 404 if not found
    user = get_object_or_404(User, email=email)
    
    # Serialize the user data
    serializer = UserSerializer(user)
    
    # Return the serialized data with a 200 OK status
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def chat(request):
    data = json.loads(request.body)
    print('\n data----',data)
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    question = data.get('text')

    # Fetch user by ID
    user = User.objects.get(id=user_id)
    print('\n user ---', user)
    # Get OpenAI response and save chat history
    system_response = get_openai_response(user, chat_id, question)

    return Response({'result': system_response}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_chat(request, chat_id):
    print('\n chat_id -------', chat_id)
    chat_history = fetch_chat(chat_id)
    serializer = MessageSerializer(chat_history)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_user_chat_history(request, user_id):
    print('\n get_user_chat_history user_id -----', user_id)
    # Ensure the user exists or return 404
    user = get_object_or_404(User, id=user_id)
    
    print('\n user', user)

    # Fetch all chat history for the user, ordered by created_at in descending order
    chat_history = Message.objects.filter(user=user,is_active=True).order_by('-created_at').values('chat_id', 'chat_label', 'created_at')
    print('\n chat_history------', chat_history)

    # Check if any chat history exists
    if not chat_history.exists():
        return Response({"detail": "No chat history found for this user."}, status=status.HTTP_404_NOT_FOUND)

    # Return the chat_id and chat_label fields
    return Response(chat_history, status=status.HTTP_200_OK)
