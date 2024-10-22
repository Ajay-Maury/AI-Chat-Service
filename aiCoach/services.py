from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from aiCoach.models import COACHING_PROMPT_TYPES, Category, CategoryLevel, CategoryLevelExample, CoachingPrompt, User, UserCallStatementsWithLevel, UserConversationHistory, UserGoal, UserPerformanceData
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from aiCoach.outputParser import ChatParser
from aiCoach.utils import CHAT_API, LLM_MODEL, parse_response
from django.core.exceptions import ObjectDoesNotExist
from collections import deque

from aiCoach.serializers import (CoachingPromptSerializer, UserCallStatementsWithLevelSerializer, 
                                 UserConversationHistorySerializer, UserGoalSerializer, UserPerformanceDataSerializer)
from langchain.globals import set_debug
from aiCoach.tasks import async_save_conversation

# set_debug(True)

print("CHAT_API", CHAT_API)


def chat_with_coach(user_name, user_id, chat_id, user_message=""):
    # Initialize conversation history
    chat_history = deque(maxlen=10)  # Keep the last 10 messages
    print("\n user_name", user_name)
    print("\n user_message", user_message)
    print("\n chat_id", chat_id)

    # Get the user's conversation history
    conversation_history = get_conversation(chat_id)
    conversation_history_serialized = UserConversationHistorySerializer(conversation_history, many=True).data

    print("\n conversation_history_serialized---", conversation_history_serialized)

    # Check if conversation history is empty
    if not conversation_history_serialized:
        print(f"No conversation history found, starting new session for chat_id: {chat_id}")
        conversation_history_serialized = [
            {
                "messages" : [],
                "summary" : {},
                "chat_label": "",
                "isGoalStepCompleted": False,
                "isRealityStepCompleted": False,
                "isOptionStepCompleted": False,
                "isOptionImprovementStepCompleted": False,
                "isWillStepCompleted": False,
            }
        ]

        chat_history = []
    
    messages = conversation_history_serialized[0].get('messages') or []

    print("\n messages-----", messages)

    # Get the last 10 messages or fewer if available
    last_messages = messages[-10:]  # Slices the last 10 messages from the list

    # Iterate through the last messages and format them
    for message in last_messages:
        # Safely check if the 'user' key exists and is not empty
        message_text = message.get('user', '')
        if message_text:  # If message_text is not empty
            chat_history.append(f"User: {message_text}")
    
        chat_history.append(f"Coach: {message['coach']}")

    # Print the formatted string
    print("\n chat_history-------", chat_history)

    
    call_statements = UserCallStatementsWithLevelSerializer(user_call_statements(user_id), many=True).data
    # print("\n call_statements", call_statements)

    user_goal = UserGoalSerializer(get_user_goal(user_id)).data
    print("\n user_goal--------", user_goal)
    
    user_performance_data = UserPerformanceDataSerializer(get_user_performance_data(user_id), many=True).data
    print("\n user_performance_data-------", user_performance_data)

    performance_data =  {
        "skills": user_performance_data,
        "last_call": call_statements
    }
    
    # Create a list of steps and their corresponding coaching functions
    steps = {
        'isGoalStepCompleted': goal_coach,
        'isRealityStepCompleted': reality_coach,
        'isOptionStepCompleted': options_coach,
        'isOptionImprovementStepCompleted': options_improvement_coach,
        'isWillStepCompleted': will_coach
    }

    # Iterate through the steps and call the respective coaching function if the step is not completed
    for step, coach_function in steps.items():
        print()
        if not conversation_history_serialized[0][step]:
            result = coach_function(user_name, user_message, user_goal, performance_data, chat_history)
            print("\n result----------", result)

            # Add the new messages to the conversation history
            if user_message and user_message.strip():  # Check if user_message is not empty or just whitespace
                messages.append({"user": user_message, "coach": result["message"]})  # Add both
            else:
                messages.append({"coach": result["message"]})  # Only add coach message

            async_save_conversation.delay(
                user_id=user_id, 
                chat_id=chat_id, 
                user_goal=user_goal, 
                messages=messages, 
                conversation_data=result, 
                previous_conversation_data=conversation_history_serialized[0]
            )

            # Return the result without waiting for the async save
            return result        



def goal_coach(user_name, user_message, goal, performance_data, conversation_history):

    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
    }

    prompt_template = get_coaching_prompt("GOAL")
    
    prompt = PromptTemplate(
        input_variables=input_variables,
        template=prompt_template,
        partial_variables=partial_variables,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = f"""
    {prompt.template}
    
    ### Conversation History - this is the conversation done with the user:- {user_name}, and coach:- Bob, get summary from it to proceed ahead:
    {''.join(conversation_history)}

    ### Do not add any message behalf of the user, if user message is empty keep it empty
    ### {user_name}'s latest message - this is the {user_name}'s message/reply to you, analyse it to get further actions:
    {user_message}
    """

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    # print("\n response", response)

    return parse_response(response.content)


def reality_coach(user_name, user_message, goal, performance_data, conversation_history): 
    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }
    
    prompt_template = get_coaching_prompt("REALITY")
    
    # Define the prompt template for the Reality coaching stage
    prompt = PromptTemplate(
        input_variables=input_variables,
        partial_variables=partial_variables,
        template=prompt_template,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = f"""
    {prompt.template}
    
    ### Conversation History - this is the conversation done with {user_name}, get summary from it to proceed ahead:
    {''.join(conversation_history)}

    ### Do not add any message behalf of the user, if user message is empty keep it empty
    ### {user_name}'s latest message - this is {user_name}'s message/reply to you, analyze it to get further actions:
    {user_message}
    """

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    # print("\n response", response)

    result = parse_response(response.content)
    # print("\n result", result)
    return result
 

# need to change prompt for this service
def options_coach(user_name, user_message, goal, performance_data, conversation_history):
    input_variables=["user_name", "goal", "performance_data", "category_level_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }

    category_levels = CategoryLevel.objects.filter(category=goal["category"])
    
    prompt_template = get_coaching_prompt("OPTIONS")

    # Define the prompt template for the Reality coaching stage
    prompt = PromptTemplate(
        input_variables=input_variables,
        partial_variables=partial_variables,
        template=prompt_template,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = f"""
    {prompt.template}
    
    ### Conversation History - this is the conversation done with {user_name}, get summary from it to proceed ahead:
    {''.join(conversation_history)}

    ### Do not add any message behalf of the user, if user message is empty keep it empty
    ### {user_name}'s latest message - this is {user_name}'s message/reply to you, analyze it to get further actions:
    {user_message}
    """

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        category_level_data=list(category_levels),
        format_instructions=partial_variables["format_instructions"]
    ))
    
    # print("\n response", response)

    result = parse_response(response.content)
    # print("\n result", result)
    return result
 

# need to change prompt for this service
def options_improvement_coach(user_name, user_message, goal, performance_data, conversation_history):
    input_variables=["user_name", "goal", "performance_data", "category_level_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }


    category_levels = CategoryLevel.objects.filter(category=goal['category'])
    
    prompt_template = get_coaching_prompt("OPTION_IMPROVEMENT")


    # Define the prompt template for the Reality coaching stage
    prompt = PromptTemplate(
        input_variables=input_variables,
        partial_variables=partial_variables,
        template=prompt_template,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = f"""
    {prompt.template}
    
    ### Conversation History - this is the conversation done with {user_name}, get summary from it to proceed ahead:
    {''.join(conversation_history)}

    ### Do not add any message behalf of the user, if user message is empty keep it empty
    ### {user_name}'s latest message - this is {user_name}'s message/reply to you, analyze it to get further actions:
    {user_message}
    """

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        category_level_data=category_levels,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    # print("\n response", response)

    result = parse_response(response.content)
    # print("\n result", result)
    return result


# need to change prompt for this service
def will_coach(user_name, user_message, goal, performance_data, conversation_history):
    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }
    
    prompt_template = get_coaching_prompt("WILL")


    # Define the prompt template for the Reality coaching stage
    prompt = PromptTemplate(
        input_variables=input_variables,
        partial_variables=partial_variables,
        template=prompt_template,
    )

    # Construct a full prompt that includes the conversation history
    full_prompt = f"""
    {prompt.template}
    
    ### Conversation History - this is the conversation done with {user_name}, get summary from it to proceed ahead:
    {''.join(conversation_history)}

    ### Do not add any message behalf of the user, if user message is empty keep it empty
    ### {user_name}'s latest message - this is {user_name}'s message/reply to you, analyze it to get further actions:
    {user_message}
    """

    # Use the LLM to generate a response
    response = LLM_MODEL.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    # print("\n response", response)

    result = parse_response(response.content)
    # print("\n result", result)
    return result
 


def save_conversation(user_id, chat_id, conversation_data, previous_conversation_data):
    try:
        user = User.objects.get(id=int(user_id))
    except ObjectDoesNotExist:
        raise ValueError(f"User with id {user_id} does not exist.")
    
    messages = conversation_data.get('messages', [])
    summary = conversation_data.get('summary', [])
    chat_label = conversation_data.get('chat_label', [])
    isGoalStepCompleted = conversation_data.get('isGoalStepCompleted', False) | previous_conversation_data.get('isGoalStepCompleted', False)
    isRealityStepCompleted = conversation_data.get('isRealityStepCompleted', False) | previous_conversation_data.get('isRealityStepCompleted', False)
    isOptionStepCompleted = conversation_data.get('isOptionStepCompleted', False) | previous_conversation_data.get('isOptionStepCompleted', False)
    isOptionImprovementStepCompleted = conversation_data.get('isOptionImprovementStepCompleted', False) | previous_conversation_data.get('isOptionImprovementStepCompleted', False)
    isWillStepCompleted = conversation_data.get('isWillStepCompleted', False) | previous_conversation_data.get('isWillStepCompleted', False)
    is_active = conversation_data.get('is_active', True)


    # Check if the  conversation_history already exists
    conversation_history_exists = UserConversationHistory.objects.filter(chat_id=chat_id, is_active=True).exists()

    # If  conversation_history exists, update the UserConversationHistorys and summary, without touching chat_label
    if conversation_history_exists:
        history_instance = UserConversationHistory.objects.filter(chat_id=chat_id, user_id=user_id).update(
            messages=messages,
            summary=summary,
            isGoalStepCompleted=isGoalStepCompleted,
            isRealityStepCompleted=isRealityStepCompleted,
            isOptionStepCompleted=isOptionStepCompleted,
            isOptionImprovementStepCompleted=isOptionImprovementStepCompleted,
            isWillStepCompleted=isWillStepCompleted,
            is_active=is_active,
        )
    else:
        # If chat does not exist, create a new one with chat_id
        history_instance = UserConversationHistory.objects.create(
            user=user,
            chat_id=chat_id,
            messages=messages,
            chat_label=chat_label,
            summary=summary,
            isGoalStepCompleted=isGoalStepCompleted,
            isRealityStepCompleted=isRealityStepCompleted,
            isOptionStepCompleted=isOptionStepCompleted,
            isOptionImprovementStepCompleted=isOptionImprovementStepCompleted,
            isWillStepCompleted=isWillStepCompleted,
            is_active=is_active,
        )

    return history_instance


def get_coaching_prompt(category):
    prompt = CoachingPrompt.objects.filter(category=category, is_active=True)
    return CoachingPromptSerializer(prompt, many=True).data[0]['prompt']


def get_conversation(chat_id, is_active=True):
    return UserConversationHistory.objects.filter(chat_id=chat_id, is_active=is_active)


def get_conversation_history_by_user(user_id, is_active=True):
        """
        Retrieve conversation history for a specific user, optionally filtering by active status.

        :param user_id: ID of the user
        :param is_active: Boolean filter to get only active conversations
        :return: List of UserConversationHistory objects
        """
        try:
            user = User.objects.get(id=user_id)
        except ObjectDoesNotExist:
            raise ValueError(f"User with id {user_id} does not exist.")
        
        conversation_history = UserConversationHistory.objects.filter(
            user=user,
            is_active=is_active
        )
        
        return conversation_history


def validate_email_address(email):
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
    print('\n user_exists ---', user_exists)

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
            is_active=True
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
        is_active=data.get('is_active', True)
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
        is_active=data.get('is_active', True)
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
        is_active=data.get('is_active', True)
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
        is_active=data.get('is_active', True)
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
    return UserPerformanceData.objects.filter(user_id=user_id, is_active= is_active)

