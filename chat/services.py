from langchain_openai import AzureChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
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
    "MAX_TOKENS": settings.CHAT_MAX_TOKENS
}


def validate_email_address(email):
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError("Invalid email address.")
    return email


def get_or_update_user(email, password, first_name='', last_name=''):
    """
    Retrieves or updates a user by email. Creates a new user if none exists.
    """
    # Validate email format
    validate_email_address(email)
    
    # Create or update user
    user, created = User.objects.update_or_create(
        email=email,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True
        }
    )
    
    # If the user was updated, ensure the password is correct
    if not created:
        if user.check_password(password):
            return user, False  # Return existing user and False (not new)
        else:
            raise ValueError("Invalid credentials")
    else:
        # If the user was created, set the password
        user.set_password(password)
        user.save()
        return user, True  # Return new user and True (is new)



def fetch_chat(chat_id):
    """
    Retrieves the chat history for a specific user.
    """
    return Message.objects.get(chat_id=chat_id, is_active=True)


def get_openai_response(user, chat_id, question):
    """
    Uses Langchain to send the user's input to Azure OpenAI and retrieves the response.
    Memory is used to maintain the context of the conversation.
    """

    # Step 1: Fetch the previous chat history for the user
    try:
        past_chat = fetch_chat(chat_id)
    except Message.DoesNotExist:
        # Handle the case where the chat does not exist
        past_chat = None
        messages = []
    
    print('\n past_chat-----', past_chat)

    # Step 2: Initialize conversation memory and load past chats
    memory = ConversationBufferMemory()

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

    # Step 3: Set up the LLM (Azure OpenAI)
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"]
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
    
    if past_chat:
        # Update the messages list from the single Message instance
        messages.append(new_message)
    else:
        # No past chat, create a new list with the current message
        messages = [new_message]

    # Step 6: Save both the user input and system response in the chat history
    create_chat(user, chat_id, messages)

    return result



def create_chat(user, chat_id, messages, chat_label=''):
    """
    Saves or updates a chat message to the database, including updated_at timestamp.
    """

    # Create or update the message in the database
    Message.objects.update_or_create(
        user=user,
        chat_id=chat_id,
        chat_label= chat_label,
        defaults={
            'messages': messages,
        }
    )


