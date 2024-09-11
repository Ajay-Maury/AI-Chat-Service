import json
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from .models import User
from .serializers import UserSerializer, MessageSerializer
from .services import get_or_update_user, fetch_chat, get_openai_response


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
def chat(request):
    data = json.loads(request.body)
    print('\n data----',data)
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    question = data.get('text')
    
    print(type(user_id))
    # Fetch user by ID
    user = User.objects.get(id=user_id)
    print('\n user ---', user)
    # Get OpenAI response and save chat history
    system_response = get_openai_response(user, chat_id, question)

    return Response({'result': system_response}, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_chat_history(request, chat_id):
    print('\n chat_id -------', chat_id)
    chat_history = fetch_chat(chat_id)
    serializer = MessageSerializer(chat_history)
    return Response(serializer.data, status=status.HTTP_200_OK)
