from collections import deque
from celery import shared_task
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from aiCoach.outputParser import ChatLabelParser, ChatParser
from langchain.memory import ConversationSummaryBufferMemory
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
        input_variables = ["conversation", "user_goal"],

        # Create a prompt template for the LLM model to generate a chat label
        prompt_template = ('''
            ### You are an AI assistant, you are here to help me.
            Read the below conversation and give me a label (name to identify the conversation) for the conversation in less than 8 words.
            The label should be subjective regarding the chat and goal.
            ### Coaching session data:
            Conversation: {conversation} \n
            Goal: {user_goal} \n\n
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
            conversation= messages,  # Concatenate all messages
            user_goal=user_goal,  # Pass the user goal
            format_instructions=partial_variables["format_instructions"]  # Include format instructions
        ))
      
        # Parse the response from the LLM model to extract the chat label
        chat_label_result = parse_response(chat_label_response.content)
        print("\n chat_label_result", chat_label_result)

        # Update the conversation data with the generated chat label
        conversation_data['chat_label'] = chat_label_result["chatLabel"]

    # Import save_conversation locally to avoid circular import issues
    from aiCoach.services import save_conversation

    # Save the updated conversation, including the chat label, messages, and summary
    save_conversation(user_id, chat_id, conversation_data, previous_conversation_data)
