# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from aiCoach.models import COACHING_PROMPT_TYPES, CoachingPrompt, User, UserConversationHistory
from aiCoach.services import (create_category, create_category_level,
  create_category_level_example, create_user_call_statements, create_user_performance_data, create_user_goal,
  get_all_categories, get_all_category_level_examples, get_all_category_levels, get_conversation, get_or_update_user, user_call_statements,
  get_user_performance_data, get_user_goal, chat_with_coach)

from aiCoach.serializers import (
    CategorySerializer,
    CategoryLevelSerializer,
    CategoryLevelExampleSerializer,
    CoachingPromptSerializer,
    UserCallStatementsWithLevelSerializer,
    UserConversationHistorySerializer,
    UserGoalSerializer,
    UserPerformanceDataSerializer,
    UserSerializer
)


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


@api_view(['GET'])
def get_chat(request, chat_id):
    print('\n chat_id -------', chat_id)
    chat_history = UserConversationHistorySerializer(get_conversation(chat_id),  many=True).data
    response = {}
    if(chat_history):
        response = chat_history[0]
    print("\n chat_history-", chat_history)
    return Response(response, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_user_chat_history(request, user_id):
    print('\n get_user_chat_history user_id -----', user_id)
    # Ensure the user exists or return 404
    user = get_object_or_404(User, id=user_id)
    
    print('\n user', user)

    # Fetch all chat history for the user, ordered by created_at in descending order
    chat_history = UserConversationHistory.objects.filter(user=user, is_active=True).order_by('-created_at').values('chat_id', 'chat_label', 'created_at')
    print('\n user_chat_history------', chat_history)

    # Check if any chat history exists
    if not chat_history.exists():
        return Response({"detail": "No chat history found for this user."}, status=status.HTTP_404_NOT_FOUND)

    # Return the chat_id and chat_label fields
    return Response(chat_history, status=status.HTTP_200_OK)


# Category Views
@api_view(['POST'])
def create_category_view(request):
    category = create_category(request.data)
    serializer = CategorySerializer(category)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_categories_view(request):
    categories = get_all_categories()
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Category Level Views
@api_view(['POST'])
def create_category_level_view(request):
    category_level = create_category_level(request.data)
    serializer = CategoryLevelSerializer(category_level)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_category_levels_view(request):
    category_levels = get_all_category_levels()
    serializer = CategoryLevelSerializer(category_levels, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Category Level Example Views
@api_view(['POST'])
def create_category_level_example_view(request):
    example = create_category_level_example(request.data)
    serializer = CategoryLevelExampleSerializer(example)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_category_level_examples_view(request):
    examples = get_all_category_level_examples()
    serializer = CategoryLevelExampleSerializer(examples, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Last Call Views
@api_view(['POST'])
def create_user_call_statements_view(request):
    last_call = create_user_call_statements(request.data)
    serializer = UserCallStatementsWithLevelSerializer(last_call)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_last_calls_view(request):
    last_calls = user_call_statements()
    serializer = UserCallStatementsWithLevelSerializer(last_calls, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# User Goal Views
@api_view(['POST'])
def create_user_goal_view(request):
    user_goal = create_user_goal(request.data)
    serializer = UserGoalSerializer(user_goal)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_user_goals_view(request, user_id):
    user_goals = get_user_goal(user_id)
    serializer = UserGoalSerializer(user_goals, many=True)
    return Response(serializer.data[0], status=status.HTTP_200_OK)


# Performance Data Views
@api_view(['POST'])
def create_user_performance_data_view(request):
    performance_data = create_user_performance_data(request.data)
    serializer = UserPerformanceDataSerializer(performance_data)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_performance_data_view(request):
    performance_data = get_user_performance_data()
    serializer = UserPerformanceDataSerializer(performance_data, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_coaching_prompts_view(request):
    coaching_prompt_data = CoachingPrompt.objects.filter(is_active=True)
    serializer = CoachingPromptSerializer(coaching_prompt_data, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
def create_coaching_prompts_view(request):
    data = request.data
    print("\n create_coaching_prompts data", data)

    category = data.get('category')
    prompt = data.get('prompt')

    if not category or not prompt:
        return Response({"error": "Category and prompt are required fields."}, status=status.HTTP_400_BAD_REQUEST)  
    
    # Validate that the category is one of the choices
    valid_categories = [choice[0] for choice in COACHING_PROMPT_TYPES]
    if category not in valid_categories:
        return Response({"error": f"Invalid category. Choose from: {valid_categories}"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create or update the CoachingPrompt
    coaching_prompt, created = CoachingPrompt.objects.update_or_create(
        category=category,
        defaults={
            'prompt': prompt,
            'is_active': data.get('is_active', True)
        }
    )

    # Serialize the result and return it
    serializer = CoachingPromptSerializer(coaching_prompt)
    if created:
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def coach_chat(request):
    data = request.data
    print("data",data)
    user_message = data.get('text', '')  # Get the user's latest message
    user_id = int(data.get('user_id'))  # Get the user_id
    chat_id = data.get('chat_id')
    
    # Ensure the user exists or return 404
    user = get_object_or_404(User, id=user_id)
    
    # Serialize user data
    user_data = UserSerializer(user).data  # No need to pass `data=user` since `user` is an instance
    
    print("\n user--", user_data)

    # Access user data correctly
    response = chat_with_coach(
        user_name=f"{user_data['first_name']} {user_data['last_name']}",
        user_id=user_data['id'],
        chat_id= chat_id,
        user_message= user_message,
    )

    return Response( response, status=status.HTTP_200_OK)

