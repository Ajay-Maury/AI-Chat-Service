from collections import deque
from celery import shared_task
from datetime import date
from django.core.exceptions import ObjectDoesNotExist
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from aiCoach.models import UserConversationHistory, User
from aiCoach.outputParser import ChatLabelParser, ChatParser
from langchain.memory import ConversationSummaryBufferMemory

from aiCoach.serializers import UserConversationHistorySerializer
from aiCoach.utils import CHAT_API, LLM_MODEL, parse_response
# from aiCoach.services import save_conversation


@shared_task
def async_save_conversation(user_id, chat_id, user_goal, messages, conversation_data, previous_conversation_data):
    """
    This function asynchronously saves the conversation data with context summary 
    and a generated label using an AI model. It uses Celery to handle the saving 
    asynchronously to avoid blocking main thread operations.
    """
    print("\n --user_id, chat_id", user_id, chat_id)
    
    # Initialize Conversation Summary Buffer Memory for tracking conversation context
    # This will allow us to summarize and track the conversation with a token limit.
    conversationSummaryMemory = ConversationSummaryBufferMemory(
        llm=LLM_MODEL,  # LLM model used for summarization
        max_token_limit=CHAT_API["CHAT_SUMMARY_MAX_TOKEN"]  # Set token limit for summary
    )

    # Iterate through the conversation messages and save them to memory
    for message in messages:
        # Safely check if the 'user' key exists and get the user message, if exists
        user_message = message.get('user', '')
        
        # Save user input and corresponding coach output (response) in memory
        conversationSummaryMemory.save_context(
           {"input": user_message},  # Save user input message
           {"output": message['coach']}  # Save coach (model) response
        )
    
    # Update conversation_data with the latest messages and the conversation summary
    conversation_data['messages'] = messages
    summary = conversationSummaryMemory.load_memory_variables({})  # Load memory (context summary)
    print("\n summary---------", summary)
    conversation_data["summary"] = summary

    # Check if a chat label has already been generated for this conversation
    if not previous_conversation_data["chat_label"]:
        # If no chat label exists, we need to generate one

        # Define the parser for extracting the chat label using Pydantic
        parser = PydanticOutputParser(pydantic_object=ChatLabelParser)
        
        # Prepare partial variables for the label format instructions
        partial_variables = {
            "format_instructions": parser.get_format_instructions(),
        }

        # Define input variables for the prompt template
        input_variables = ["conversation", "user_goal", "current_date"]

        current_date = date.today()

        # Create a prompt template for the LLM model to generate a chat label
        prompt_template = ('''
            ### You are an AI assistant, you are here to help me.
            Read the below conversation and give me a label (name to identify the conversation) for the conversation in less than 8 words.
            The label should be subjective regarding the chat and goal.
            ### Coaching session data:
            Conversation: {conversation} \n
            Goal: {user_goal} \n\n
            current_data: {current_date}\n\n
            label should start with the date of the conversation and information about user goal with the user conversation.
            ### Instruction for your output format:
            \nOutput: {format_instructions}\n
        ''')

        # Create the prompt object for the language model (LLM)
        prompt = PromptTemplate(
            input_variables=input_variables,
            template=prompt_template,
            partial_variables=partial_variables,
        )

        # Invoke the LLM model with the formatted prompt to generate a chat label
        chat_label_response = LLM_MODEL.invoke(prompt.format(
            conversation=messages,  # Concatenate all messages
            user_goal=user_goal,  # Pass the user goal
            current_date=current_date,
            format_instructions=partial_variables["format_instructions"]  # Include format instructions
        ))
      
        # Parse the response from the LLM model to extract the chat label
        chat_label_result = parse_response(chat_label_response.content)
        print("\n chat_label_result", chat_label_result)

        # Update the conversation data with the generated chat label
        conversation_data['chat_label'] = chat_label_result["chatLabel"]

    # Save the updated conversation, including the chat label, messages, and summary
    save_conversation(user_id, chat_id, conversation_data, previous_conversation_data)


def save_conversation(user_id, chat_id, conversation_data, previous_conversation_data):
    print(" inside save_conversation ")
    print(user_id)
    print(type(user_id))
    print(chat_id)
    print(type(chat_id))
    print(conversation_data)
    print(type(conversation_data))
    print(previous_conversation_data)
    print(type(previous_conversation_data))

    try:
        user = User.objects.get(id=user_id)
        print("user in save_conversation ", user )
    except ObjectDoesNotExist:
        raise ValueError(f"User with id {user_id} does not exist.")
    print(" inside save_conversation2 ")

    messages = conversation_data.get('messages', [])
    summary = conversation_data.get('summary', [])
    chat_label = conversation_data.get('chat_label', [])
    isGoalStepCompleted = conversation_data.get('isGoalStepCompleted', False) | previous_conversation_data.get(
        'isGoalStepCompleted', False)
    isRealityStepCompleted = conversation_data.get('isRealityStepCompleted', False) | previous_conversation_data.get(
        'isRealityStepCompleted', False)
    isOptionStepCompleted = conversation_data.get('isOptionStepCompleted', False) | previous_conversation_data.get(
        'isOptionStepCompleted', False)
    isOptionImprovementStepCompleted = conversation_data.get('isOptionImprovementStepCompleted',
                                                             False) | previous_conversation_data.get(
        'isOptionImprovementStepCompleted', False)
    isWillStepCompleted = conversation_data.get('isWillStepCompleted', False) | previous_conversation_data.get(
        'isWillStepCompleted', False)
    is_active = conversation_data.get('is_active', True)

    # Check if the  conversation_history already exists
    conversation_history_exists = UserConversationHistory.objects.filter(chat_id=chat_id, is_active=True).exists()

    # If  conversation_history exists, update the UserConversationHistorys and summary, without touching chat_label
    if conversation_history_exists:
        print('UserConversationHistory just updation')

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
        print('UserConversationHistory new creation')
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
    print(UserConversationHistorySerializer(history_instance).data)
    return UserConversationHistorySerializer(history_instance).data