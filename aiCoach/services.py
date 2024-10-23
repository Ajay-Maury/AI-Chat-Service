from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from aiCoach.models import (
    COACHING_PROMPT_TYPES,
    Category,
    CategoryLevel,
    CategoryLevelExample,
    CoachingPrompt,
    User,
    UserCallStatementsWithLevel,
    UserConversationHistory,
    UserGoal,
    UserPerformanceData,
)
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from aiCoach.outputParser import ChatParser
from aiCoach.utils import CHAT_API, LLM_MODEL, parse_response
from collections import deque
from aiCoach.serializers import (
    CoachingPromptSerializer,
    UserCallStatementsWithLevelSerializer,
    UserConversationHistorySerializer,
    UserGoalSerializer,
    UserPerformanceDataSerializer,
)
from langchain.globals import set_debug
from aiCoach.tasks import async_save_conversation

# Uncomment for debugging
# set_debug(True)

print("CHAT_API:", CHAT_API)


def chat_with_coach(user_name, user_id, chat_id, user_message=""):
    """
    Main function to handle chat with the coach.
    """
    # Initialize conversation history
    chat_history = deque(maxlen=10)  # Keep the last 10 messages

    print("User Name:", user_name)
    print("User Message:", user_message)
    print("Chat ID:", chat_id)

    # Get the user's conversation history
    conversation_history = get_conversation(chat_id)
    conversation_history_serialized = UserConversationHistorySerializer(
        conversation_history, many=True
    ).data

    print("Serialized Conversation History:", conversation_history_serialized)

    # Check if conversation history is empty
    if not conversation_history_serialized:
        print(f"No conversation history found, starting new session for chat_id: {chat_id}")
        conversation_history_serialized = [
            {
                "messages": [],
                "summary": {},
                "chat_label": "",
                "isGoalStepCompleted": False,
                "isRealityStepCompleted": False,
                "isOptionStepCompleted": False,
                "isOptionImprovementStepCompleted": False,
                "isWillStepCompleted": False,
            }
        ]
        chat_history = []
    else:
        messages = conversation_history_serialized[0].get('messages') or []
        print("Messages:", messages)

        # Get the last 10 messages or fewer if available
        last_messages = messages[-10:]  # Slices the last 10 messages from the list

        # Iterate through the last messages and format them
        for message in last_messages:
            # Safely check if the 'user' key exists and is not empty
            message_text = message.get('user', '')
            if message_text:  # If message_text is not empty
                chat_history.append(f"User: {message_text}")
            if 'coach' in message:
                chat_history.append(f"Coach: {message['coach']}")

    print("Chat History:", chat_history)

    # Get call statements, user goal, and performance data
    call_statements = UserCallStatementsWithLevelSerializer(
        user_call_statements(user_id), many=True
    ).data
    user_goal = UserGoalSerializer(get_user_goal(user_id)).data
    user_performance_data = UserPerformanceDataSerializer(
        get_user_performance_data(user_id), many=True
    ).data

    print("User Goal:", user_goal)
    print("User Performance Data:", user_performance_data)

    performance_data = {
        "skills": user_performance_data,
        "last_call": call_statements,
    }

    # Create a list of steps and their corresponding status keys
    steps = [
        ('GOAL', 'isGoalStepCompleted'),
        ('REALITY', 'isRealityStepCompleted'),
        ('OPTIONS', 'isOptionStepCompleted'),
        ('OPTION_IMPROVEMENT', 'isOptionImprovementStepCompleted'),
        ('WILL', 'isWillStepCompleted'),
    ]

    # Iterate through the steps and call the generalized coach function
    for step_type, step_key in steps:
        print(f"Processing step: {step_type}")
        if not conversation_history_serialized[0][step_key]:
            result = coach(
                step_type=step_type,
                user_name=user_name,
                user_message=user_message,
                goal=user_goal,
                performance_data=performance_data,
                conversation_history=chat_history,
            )

            print("Result:", result)

            # Add the new messages to the conversation history
            if user_message and user_message.strip():  # Check if user_message is not empty or just whitespace
                messages.append({"user": user_message, "coach": result["message"]})  # Add both
            else:
                messages.append({"coach": result["message"]})  # Only add coach message

            # Save the conversation asynchronously
            async_save_conversation.delay(
                user_id=user_id,
                chat_id=chat_id,
                user_goal=user_goal,
                messages=messages,
                conversation_data=result,
                previous_conversation_data=conversation_history_serialized[0],
            )

            # Return the result without waiting for the async save
            return result

    # If all steps are completed, continue the conversation or conclude
    result = {
        "message": "We've completed all coaching steps. How else can I assist you today?"
    }
    print("Result:", result)
    return result


def coach(step_type, user_name, user_message, goal, performance_data, conversation_history):
    """
    Generalized coaching function to handle different coaching steps.
    """
    input_variables = ["user_name", "goal", "performance_data"]
    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
    }

    # Additional variables for OPTIONS and OPTION_IMPROVEMENT steps
    if step_type in ["OPTIONS", "OPTION_IMPROVEMENT"]:
        input_variables.append("category_level_data")
        category_levels = CategoryLevel.objects.filter(category=goal["category"])
        category_level_data = list(category_levels.values())
    else:
        category_level_data = None

    prompt_template = get_coaching_prompt(step_type)

    prompt = PromptTemplate(
        input_variables=input_variables,
        partial_variables=partial_variables,
        template=prompt_template,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = (
        f"{prompt.template} ### Conversation History: This is the conversation done with {user_name}, "
        f"get a summary from it to proceed ahead: {''.join(conversation_history)} "
        f"### Do not add any message on behalf of the user; if the user's message is empty, keep it empty. "
        f"### {user_name}'s latest message: This is {user_name}'s message/reply to you. Analyze it to get further actions: {user_message}"
    )

    # Prepare the prompt parameters
    prompt_params = {
        "user_name": user_name,
        "goal": goal,
        "performance_data": performance_data,
        "format_instructions": partial_variables["format_instructions"],
    }

    if category_level_data:
        prompt_params["category_level_data"] = category_level_data

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(**prompt_params))

    # Parse and return the response
    result = parse_response(response.content)
    return result


def get_coaching_prompt(category):
    """
    Retrieves the coaching prompt for the given category.
    """
    prompt = CoachingPrompt.objects.filter(category=category, is_active=True).first()
    if not prompt:
        raise ValueError(f"No active coaching prompt found for category: {category}")
    return prompt.prompt


def get_conversation(chat_id, is_active=True):
    """
    Retrieves conversation history for the given chat ID.
    """
    return UserConversationHistory.objects.filter(chat_id=chat_id, is_active=is_active)


def get_conversation_history_by_user(user_id, is_active=True):
    """
    Retrieves conversation history for a specific user, optionally filtering by active status.
    """
    try:
        user = User.objects.get(id=user_id)
    except ObjectDoesNotExist:
        raise ValueError(f"User with id {user_id} does not exist.")
    conversation_history = UserConversationHistory.objects.filter(
        user=user, is_active=is_active
    )
    return conversation_history


def validate_email_address(email):
    """
    Validates an email address.
    """
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError("Invalid email address.")
    return email


def get_or_update_user(email, password, first_name='', last_name=''):
    """
    Retrieves or creates a user by email. Updates only password if the user exists.
    """
    # Validate email format
    validate_email_address(email)

    # Check if the user already exists
    user_exists = User.objects.filter(email=email).exists()
    print('User exists:', user_exists)
    if user_exists:
        # If the user exists, update only the password
        user = User.objects.get(email=email)
        if user.check_password(password):
            return user, False  # Return existing user and False (not new)
        else:
            raise ValueError("Invalid credentials")
    else:
        # If the user does not exist, create a new user
        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        return user, True  # Return new user and True (is new)


# Category services
def create_category(data):
    category = Category.objects.create(
        category=data['category'],
        definition=data.get('definition', ''),
        instruction=data.get('instruction', ''),
        examples=data.get('examples', ''),
        invalid_examples=data.get('invalid_examples', ''),
        is_active=data.get('is_active', True),
    )
    return category


def get_all_categories():
    return Category.objects.filter(is_active=True)


# CategoryLevel services
def create_category_level(data):
    category = Category.objects.get(id=data['category'])
    level = CategoryLevel.objects.create(
        category=category,
        level=data['level'],
        description=data.get('description', ''),
        examples=data.get('examples', ''),
        invalid_examples=data.get('invalid_examples', ''),
        is_active=data.get('is_active', True),
    )
    return level


def get_all_category_levels():
    return CategoryLevel.objects.filter(is_active=True)


# CategoryLevelExample services
def create_category_level_example(data):
    category_level = CategoryLevel.objects.get(id=data['category_level'])
    example = CategoryLevelExample.objects.create(
        category_level=category_level,
        example_text=data['example_text'],
        reason=data.get('reason', ''),
    )
    return example


def get_all_category_level_examples():
    return CategoryLevelExample.objects.all()


# UserCallStatementsWithLevel services
def create_user_call_statements(data):
    last_call = UserCallStatementsWithLevel.objects.create(
        user_id=data['user'],  # Assuming you pass the user ID
        statement=data['statement'],
        category=data['category'],
        level=data['level'],
        reason=data['reason'],
        confidence_score=data['confidence_score'],
        is_active=data.get('is_active', True),
    )
    return last_call


def user_call_statements(user_id, is_active=True):
    return UserCallStatementsWithLevel.objects.filter(user_id=user_id, is_active=is_active)


# UserGoal services
def create_user_goal(data):
    user_goal = UserGoal.objects.create(
        user_id=data['user'],
        category=data['category'],
        initial_level=data['initial_level'],
        current_level=data['current_level'],
        goal_level=data['goal_level'],
        goal_confirmation=data.get('goal_confirmation', True),
        is_active=data.get('is_active', True),
    )
    return user_goal


def get_user_goal(user_id, is_active=True):
    return UserGoal.objects.filter(user_id=user_id, is_active=is_active).first()


# UserPerformanceData services
def create_user_performance_data(data):
    performance_data = UserPerformanceData.objects.create(
        user_id=data['user'],
        skill=data['skill'],
        date=data['date'],
        not_observed=data['not_observed'],
        foundational=data['foundational'],
        developing=data['developing'],
        accomplished=data['accomplished'],
        combined_DA=data['combined_DA'],
    )
    return performance_data


def get_user_performance_data(user_id, is_active=True):
    return UserPerformanceData.objects.filter(user_id=user_id, is_active=is_active)