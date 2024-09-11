from langchain_openai import AzureChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryBufferMemory, ConversationBufferWindowMemory
from .models import Message, User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.conf import settings  # Import the settings to access environment variables
import re

# Azure OpenAI Configurations (from your settings)
CHAT_API = {
    "MODEL_NAME": settings.CHAT_MODEL_NAME,  # Azure OpenAI Model
    "TEMPERATURE": settings.CHAT_TEMPERATURE,
    "MAX_TOKENS": settings.CHAT_MAX_TOKENS,
    "CONVERSATION_BUFFER_WINDOW_SIZE": 5,
    "CHAT_SUMMARY_MAX_TOKEN": settings.CHAT_SUMMARY_MAX_TOKEN,
}


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
    print('\n user_exists ---',user_exists)

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


def fetch_chat(chat_id):
    """
    Retrieves the chat history for a specific user.
    Returns None if no matching chat is found.
    """
    chat = Message.objects.filter(chat_id=chat_id, is_active=True).first() or {}
    print('\n chat', chat)
    return chat


def get_openai_response(user, chat_id, question):
    """
    Uses Langchain to send the user's input to Azure OpenAI and retrieves the response.
    Memory is used to maintain the context of the conversation.
    """

    # Step 1: Fetch the previous chat history for the user
    past_chat = fetch_chat(chat_id) or None
    messages = []
    
    # Step 2: Set up the LLM (Azure OpenAI)
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"]
    )

    # Step 3: Initialize conversation memory and load past chats
    memory = ConversationBufferWindowMemory(k=CHAT_API['CONVERSATION_BUFFER_WINDOW_SIZE'])
    conversationSummaryMemory= ConversationSummaryBufferMemory(llm=llm, max_token_limit=CHAT_API["CHAT_SUMMARY_MAX_TOKEN"])

    if past_chat:
        # Extract messages from the single Message instance
        messages = past_chat.messages
        for message in messages:
            # Assuming each message is structured like { "question": "ABC", "result": "XYZ" }
            memory.save_context(
                {
                    "input": message.get("question", "")
                },
                {
                    "output": message.get("result", "")
                }
            )

            conversationSummaryMemory.save_context(
                {
                    "input": message.get("question", "")
                },
                {
                    "output": message.get("result", "")
                }
            )    

    # Step 4: Generate the response using the memory context
    conversation = ConversationChain(
        llm=llm, 
        memory=memory,
        verbose=True
    )

    # Get the response from the LLM
    result = conversation.predict(input=question)
    print('result ---', result)
    
    # Step 5: Append the new question and response to messages
    new_message = {
        "question": question,
        "result": result
    }
    
    conversationSummaryMemory.save_context(
        {
            "input": question
        },
        {
            "output": result
        }
    )
    
    # Step 6: get the chat summary
    summary = conversationSummaryMemory.load_memory_variables({})
    
    print('\n summary-----',summary)
    
    if past_chat:
        # Update the messages list from the single Message instance
        messages.append(new_message)
    else:
        # No past chat, create a new list with the current message
        messages = [new_message]

    # Step 7: Save both the user input and system response in the chat history with summary
    create_chat(user, chat_id, messages, summary, chat_label=question)

    return result



def create_chat(user, chat_id, messages, summary='', chat_label=''):
    """
    Saves or updates a chat message to the database, without updating chat_label after creation.
    """

    # Check if the chat already exists
    chat_exists = Message.objects.filter(chat_id=chat_id).exists()

    # If chat exists, update the messages and summary, without touching chat_label
    if chat_exists:
        Message.objects.filter(chat_id=chat_id).update(
            messages=messages,
            summary=summary
        )
    else:
        # If chat does not exist, create a new one with chat_label
        Message.objects.create(
            user=user,
            chat_id=chat_id,
            chat_label=chat_label,
            messages=messages,
            summary=summary
        )


