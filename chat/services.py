from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.messages import HumanMessage, SystemMessage,trim_messages
from chat.serializers import MessageSerializer, UserSerializer
from .models import Message, User
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.conf import settings  # Import the settings to access environment variables
from langchain_openai import AzureChatOpenAI
from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory,
)
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import BaseMessage, AIMessage

# Azure OpenAI Configurations (from your settings)
CHAT_API = {
    "MODEL_DEPLOYMENT": settings.AZURE_OPENAI_DEPLOYMENT_NAME,  # Azure OpenAI Model
    "MODEL_NAME": settings.AZURE_OPENAI_MODEL_NAME,
    "OPENAI_ENDPOINT": settings.AZURE_OPENAI_ENDPOINT,
    "OPENAI_API_VERSION": settings.AZURE_OPENAI_API_VERSION,
    "TEMPERATURE": settings.AZURE_OPENAI_CHAT_TEMPERATURE,
    "MAX_TOKENS": settings.AZURE_OPENAI_CHAT_MAX_TOKENS,
    "TRIM_MAX_TOKENS": settings.AZURE_OPENAI_CHAT_MAX_TRIM_TOKENS,
    "CONVERSATION_BUFFER_WINDOW_SIZE": settings.AZURE_OPENAI_CONVERSATION_BUFFER_WINDOW_SIZE,
    "CHAT_SUMMARY_MAX_TOKEN": settings.AZURE_OPENAI_CHAT_SUMMARY_MAX_TOKEN,
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


def fetch_chat(chat_id):
    """
    Retrieves the chat history for a specific user.
    Returns None if no matching chat is found.
    """
    chat = Message.objects.filter(chat_id=chat_id, is_active=True).first() or {}
    print('\n chat', chat)
    return chat


def get_openai_response(user, chat_id, question):
    
    # Step 1: Fetch user data and past chat history
    user_data = UserSerializer(user).data  # Serialize the user data
    print('user_data---', user_data['id'])  # Access the 'id' field

    past_chat = fetch_chat(chat_id) or None  # Fetch previous chat if available
    print('\n past_chat', past_chat)
    
    messages = []  # Initialize messages list
    past_messages = []  # To store and process past chat messages

    # Step 2: Set up the LLM (Azure OpenAI) with necessary parameters
    model = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )
    
    # Initialize Conversation Summary Buffer Memory for tracking conversation context
    conversationSummaryMemory = ConversationSummaryBufferMemory(
        llm=model, 
        max_token_limit=CHAT_API["CHAT_SUMMARY_MAX_TOKEN"]
    )
    
    # Step 3: If there's a past chat, load its messages into the conversation context
    if past_chat:
        past_messages = MessageSerializer(past_chat).data.get('messages', [])
        print('\n past_messages:---', past_messages)

        for msg in past_messages:
            # Add past human and AI messages to the message list
            messages.append(HumanMessage(content=msg.get("question", "")))
            messages.append(AIMessage(content=msg.get("result", "")))

            # Save the conversation history to memory
            conversationSummaryMemory.save_context(
                {"input": msg.get("question", "")},
                {"output": msg.get("result", "")}
            )

    # Step 4: Set up the prompt for the model with a message placeholder
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant. Answer all questions to the best of your ability."),
            MessagesPlaceholder(variable_name="messages"),  # Placeholder for message history
            ("human", "{{input}}"),  # The human query/input
        ]
    )

    # Step 5: Trim the conversation if it exceeds the token limit
    trimmer = trim_messages(
        max_tokens=CHAT_API['TRIM_MAX_TOKENS'],
        strategy="last",
        token_counter=model,
        include_system=True,
        allow_partial=True,
        start_on="human",
    )
    
    trimmed_messages = trimmer.invoke(messages)  # Apply trimming to messages
    print('\n trimmed messages', trimmed_messages)

    # Step 6: Build the chain for invoking the model with the trimmed messages and prompt
    chain = (
        RunnablePassthrough.assign(messages=itemgetter("messages") | trimmer)  # Trimmed message assignment
        | prompt  # Apply the prompt template
        | model   # Send the final prompt to the model for a response
    )

    # Step 7: Invoke the model with the current question appended to the trimmed message history
    response = chain.invoke(
        {
            "messages": trimmed_messages + [HumanMessage(content=question)],
        }
    )
    
    print('\n messages--', messages)

    # Step 8: Save the latest conversation to memory
    conversationSummaryMemory.save_context(
        {"input": question},  # Save user input
        {"output": response.content}  # Save model response
    )
    
    # Append the latest interaction to the past messages for future context
    past_messages.append({
        "question": question,
        "result": response.content
    })

    # Step 9: Generate a summary of the conversation from the memory
    summary = conversationSummaryMemory.load_memory_variables({})
    print('\n summary-----', summary)

    # Step 10: Save the updated chat history and summary in the database
    create_chat(user, chat_id, past_messages, summary, chat_label=question)

    return response.content  # Return the model's response


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


