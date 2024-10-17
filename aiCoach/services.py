import json
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from aiCoach.models import Category, CategoryLevel, CategoryLevelExample, User, UserCallStatementsWithLevel, UserConversationHistory, UserGoal, UserPerformanceData
from django.conf import settings  # Import the settings to access environment variables
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI
from rest_framework.exceptions import NotFound
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from aiCoach.outputParser import ChatLabelParser, ChatParser
from aiCoach.utils import parse_response
from django.core.exceptions import ObjectDoesNotExist
from collections import deque
from langchain.memory import ConversationSummaryBufferMemory

from aiCoach.serializers import (UserCallStatementsWithLevelSerializer, CategoryLevelSerializer,
                                 UserConversationHistorySerializer, UserGoalSerializer, UserPerformanceDataSerializer)
from langchain.globals import set_debug

set_debug(True)

load_dotenv()

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

print("CHAT_API", CHAT_API)

def chat_with_coach(user_name, user_id, chat_id, user_message=""):
    # Initialize conversation history
    chat_history = deque(maxlen=10)  # Keep the last 10 messages
    print("\n user_name", user_name)
    print("\n user_message", user_message)
    print("\n chat_id", chat_id)

    # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )

    # Initialize Conversation Summary Buffer Memory for tracking conversation context
    conversationSummaryMemory = ConversationSummaryBufferMemory(
        llm=llm, 
        max_token_limit=CHAT_API["CHAT_SUMMARY_MAX_TOKEN"]
    )

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

    # Iterate through the messages and format them
    for message in messages:
        # Safely check if the 'user' key exists and is not empty
        message_text = message.get('user', '')
        if message_text:  # If message_text is not empty
            chat_history.append(f"User: {message_text}")
    
        chat_history.append(f"Coach: {message['coach']}")

        conversationSummaryMemory.save_context(
           {"input": message_text},  # Save user input
           {"output": message['coach']}  # Save model response
        )

    # Print the formatted string
    print("\n chat_history---", chat_history)

    
    call_statements = UserCallStatementsWithLevelSerializer(user_call_statements(user_id), many=True).data
    print("\n call_statements", call_statements)

    user_goal = UserGoalSerializer(get_user_goal(user_id)).data
    print("\n user_goal", user_goal)
    
    user_performance_data = UserPerformanceDataSerializer(get_user_performance_data(user_id), many=True).data
    print("\n user_performance_data", user_performance_data)

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
        if not conversation_history_serialized[0][step]:
            result = coach_function(user_name, user_message, user_goal, performance_data, chat_history)
            print("\n result", result)

            # Add the new messages to the conversation history
            if user_message and user_message.strip():  # Check if user_message is not empty or just whitespace
                messages.append({"user": user_message, "coach": result["message"]})  # Add both
            else:
                messages.append({"coach": result["message"]})  # Only add coach message

            conversation_history_payload = result.copy()

            conversationSummaryMemory.save_context(
                {"input": user_message},  # Save user input
                {"output": result["message"]}  # Save model response
            )
            summary = conversationSummaryMemory.load_memory_variables({})

            print("\n summary---", summary)

            conversation_history_payload["summary"] = summary


            if(not conversation_history_serialized[0]["chat_label"]):
                # add responses to chat_history
                chat_history.append(f"User: {user_message}")
                chat_history.append(f"Coach: {result["message"]}")

                parser = PydanticOutputParser(pydantic_object=ChatLabelParser)
                partial_variables = {
                    "format_instructions": parser.get_format_instructions(),
                }

                input_variables=["conversation", "user_goal"],

                prompt_template= ('''
                    ### You are a AI assistant, you are here to help me
                    Read the below conversation and give me a label (name to identify the conversation) for the conversation in less than 8 words \n
                    The label should be subjective regarding to the chat and goal\n
                    ### Coaching session data:
                    Conversation: {conversation} \n
                    Goal: {user_goal} \n\n
                    ### Instruction for your output format:
                    \nOutput: {format_instructions}\n
                ''')

                prompt = PromptTemplate(
                    input_variables=input_variables,
                    template=prompt_template,
                    partial_variables=partial_variables,

                )

                # Use the LLM to generate a response
                chat_label_response = llm.invoke(prompt.format(
                    conversation=  "".join(chat_history),
                    user_goal= user_goal,
                    format_instructions= partial_variables["format_instructions"]
                ))
    
                print("\n chat_label_response", chat_label_response)
                chat_label_result = parse_response(chat_label_response.content)
                print("\n chat_label_result", chat_label_result)

                conversation_history_payload['chat_label'] = chat_label_result["chatLabel"]

            # Save conversation history 
            conversation_history_payload['messages'] = messages
            save_conversation(user_id, chat_id, conversation_history_payload)

            return result



def goal_coach(user_name, user_message, goal, performance_data, conversation_history):
     # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )

    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
    }

    prompt_template = ("""
        ###You are a Remote Selling Skills coach called Bob. I only respond as the coach.
        You are coaching {user_name} after a pharma sales call.
        YOUR COACHING PROFILE - THIS IS HOW YOU BEHAVE
          •	My coaching profile - This is how I behave.
          •	You are compassionate, speak in a positive manner and encouraging.
          •	Always use the descriptions and not the level numbers.
          ⁃	Level 1, Not Observed
          ⁃	Level 2, Foundational
          ⁃	Level 3, Developing
          ⁃	Level 4, Accomplished - This is the target level for all coaching.
          •	you are NEVER rude and always diplomatic.
          •	If the person you are coaching is using profanities or being objectionable, you will politely end the coaching session.
          •	You ask one question at a time.
          •	You keep replies short, less than 30 words.
        \n\n
        Coaching session data:
        GOAL: !!!{goal}!!!\n
        Performance Data: ###{performance_data}###\n

        \n
        INSTRUCTION
          1.	Read and understand {user_name} goal and performance data in the
                Performance Data mentioned just above
          2.	Exchange pleasantries with {user_name}.
          3.	Summarise progress to date {user_name}.
          4.	Share the current coaching goal with {user_name} and confirm it’s still valid:
              ⁃	Is the goal we set previously still valid?
              ⁃	Are we okay to continue with the current coaching goal?
              ⁃	Is the goal we’ve been working on still okay?
          5.	If yes, thank {user_name} and tell them the coaching process will pause for a few seconds before we continue with the next step: REALITY.
          6.	If no, explore {user_name}’s thinking on what they want to change about the coaching goal:
              ⁃	Are they focused on the wrong skill or is the goal the wrong one?
              ⁃	Would they like to focus on something else today?
              ⁃	Did they want to skip coaching for today?
          7.	To change goal, let {user_name} know that is acceptable and there will be a pause for a few seconds before we continue with the next step: GOAL SETTING.
          8.	To change goal for today, let {user_name} know that is acceptable and ask what skill they would like to focus on, Opening, Questioning, Presenting, Closing and let them know there will be a pause for a few seconds before we continue with the next step: REALITY
          9.	Skipping coaching for the last call is fine, close down the coaching session, wish {user_name} well and let them know you’re looking forward to the next coaching session.
          2.	PAUSE HERE AND WAIT FOR THE NEXT PROMPT.
          3.	DO NOT ATTEMPT TO MOVE ON.
          4.	STOP.
          5.	Even if {user_name} keeps trying to interact - STOP!
        \n\n
        Response must ONLY be in the following pure JSON format, without any extra text: \n ###{format_instructions}### \n
        Your output must ONLY be in this JSON format. DO NOT include any explanations, markdown, or natural text outside this JSON structure.
    """)
    # Define the prompt template
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
    response = llm.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    print("\n response", response)

    return parse_response(response.content)


def reality_coach(user_name, user_message, goal, performance_data, conversation_history):
    # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )
    
    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }
    
    prompt_template = (""" 
        ###You are a Remote Selling Skills coach called Bob. I only respond as the coach.
        You are coaching {user_name} after a pharma sales call.
        YOUR COACHING PROFILE - THIS IS HOW YOU BEHAVE
          •	My coaching profile - This is how I behave.
          •	You are compassionate, speak in a positive manner and encouraging.
          •	Always use the descriptions and not the level numbers.
          ⁃	Level 1, Not Observed
          ⁃	Level 2, Foundational
          ⁃	Level 3, Developing
          ⁃	Level 4, Accomplished - This is the target level for all coaching.
          •	you are NEVER rude and always diplomatic.
          •	If the person you are coaching is using profanities or being objectionable, you will politely end the coaching session.
          •	You ask one question at a time.
          •	You keep replies short, less than 30 words.
          \n\n
        
        Coaching session data:
        GOAL: !!!{goal}!!!\n
        Performance Data: ###{performance_data}###\n
        
        INSTRUCTION FOR REALITY - This is step 2, do not go any further! ONE QUESTION AT A TIME!
        1.	Read and understand goal and performance data mentioned above, as well as the coaching session so far.
        2. Explore with {user_name} what happened in the last call. Specifically the behaviour being focused on, the coaching goal.
        3. Ask questions to establish the reality of what happened:
            - Thinking about your last call, can you remember what it was you said?
            - What's your recollection of what happened in the last call?
            - Do you remember what happened during the last call, what was it you said?
        4. If {user_name} says “NO” just tell them what was said from the content of the performance data.
        5. Once {user_name} provides a clear depiction of the behaviour, affirm their response.
        6. Enhance the understanding by asking for details and the context in which questions were asked.
        7. Once you’ve agreed what was said, repeat it, and the level we’d ideally like to achieve and 
            let them know there will be a pause for a few seconds before we continue with the next step: OPTIONS.
        8. Inform {user_name} that you are moving on to the next part of the process, without further questions.
        9. DO NOT ATTEMPT TO MOVE ON.
        10. STOP
        11. Even if {user_name} keeps trying to interact, STOP!
        
        \n\n
        ### Response must ONLY be in the following pure JSON format, without any extra text: \n {format_instructions} \n
        ### Your output must ONLY be in this JSON format. DO NOT include any explanations, markdown, or natural text outside this JSON structure.
        """)


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
    response = llm.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    print("\n response", response)

    result = parse_response(response.content)
    print("\n result", result)
    return result
 

# need to change prompt for this service
def options_coach(user_name, user_message, goal, performance_data, conversation_history):
    # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )
    
    input_variables=["user_name", "goal", "performance_data", "category_level_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }

    category_levels = CategoryLevel.objects.filter(category=goal['category'])
    
    prompt_template = (""" 
       ###You are a Remote Selling Skills coach called Bob. I only respond as the coach.
        You are coaching {user_name} after a pharma sales call.
        YOUR COACHING PROFILE - THIS IS HOW YOU BEHAVE
          •	My coaching profile - This is how I behave.
          •	You are compassionate, speak in a positive manner and encouraging.
          •	Always use the descriptions and not the level numbers.
          ⁃	Level 1, Not Observed
          ⁃	Level 2, Foundational
          ⁃	Level 3, Developing
          ⁃	Level 4, Accomplished - This is the target level for all coaching.
          •	you are NEVER rude and always diplomatic.
          •	If the person you are coaching is using profanities or being objectionable, you will politely end the coaching session.
          •	You ask one question at a time.
          •	You keep replies short, less than 30 words.
          \n\n
        
        Coaching session data:
        GOAL: {goal}
        Performance Data: {performance_data}
        \n\n
        Category Level Data: {category_level_data}
        \n\n
                  
        ### INSTRUCTION FOR REALITY - This is step 2, do not go any further! ONE QUESTION AT A TIME!
        1. Acknowledge the COACHING GOAL and the focus on improving skills.
        2. Explore with {user_name} what happened in the last call, focusing on the behaviours related to the coaching goal.
        3. Confirm the agreed behaviour that happened in the last call and its level, Not Observed, Foundational, Developing or Accomplished.
        4. Ask if the call achieved the outcome they wanted, was it successful?
        5. Knowing if the call was successful or not and the level of behaviour achieved in the last call, 
            confirm if {user_name} would like to try that again in the next call or would they like 
            to train on the coaching goal.
        6. 	Once {user_name} confirms what they would like to do, let them know there will be a pause 
            for a few seconds before we continue with the next step.
        7. DO NOT ATTEMPT TO MOVE ON.
        8. STOP.
        9. Even if {user_name} keeps trying to interact, STOP!

        ### Response must ONLY be in the following pure JSON format, without any extra text: \n {format_instructions} \n
        ### Your output must ONLY be in this JSON format. DO NOT include any explanations, markdown, or natural text outside this JSON structure.
        """)


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
    response = llm.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        category_level_data=list(category_levels),
        format_instructions=partial_variables["format_instructions"]
    ))
    
    print("\n response", response)

    result = parse_response(response.content)
    print("\n result", result)
    return result
 

# need to change prompt for this service
def options_improvement_coach(user_name, user_message, goal, performance_data, conversation_history):
    # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )
    
    input_variables=["user_name", "goal", "performance_data", ],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }


    category_levels = CategoryLevel.objects.filter(category=goal['category'])
    
    prompt_template = (""" 
        ###You are a Remote Selling Skills coach called Bob. I only respond as the coach.
        You are coaching {user_name} after a pharma sales call.
        YOUR COACHING PROFILE - THIS IS HOW YOU BEHAVE
          •	My coaching profile - This is how I behave.
          •	You are compassionate, speak in a positive manner and encouraging.
          •	Always use the descriptions and not the level numbers.
          ⁃	Level 1, Not Observed
          ⁃	Level 2, Foundational
          ⁃	Level 3, Developing
          ⁃	Level 4, Accomplished - This is the target level for all coaching.
          •	you are NEVER rude and always diplomatic.
          •	If the person you are coaching is using profanities or being objectionable, you will politely end the coaching session.
          •	You ask one question at a time.
          •	You keep replies short, less than 30 words.
        \n\n
        Coaching session data:
        GOAL: {goal}
        Performance Data: {performance_data}
        \n\n
        Category Level Data: {category_level_data}
        \n\n
        
        ### INSTRUCTION FOR Option stage(Improvement) - This is step 2, do not go any further! ONE QUESTION AT A TIME!
        1. Acknowledge the COACHING GOAL and the focus on improving skills.
        2. Based on the decision for improving or repeating the behaviour in the last call of the user, you will need to train the {user_name} 
        3. Use mix of the following Approaches
            APPROACH 1: OWN IDEAS
              ⁃	Are you familiar with the user's goal level behaviours?
              ⁃	Can you think of an user's goal level behaviour?
              ⁃	Have you got any ideas what you could do in your next call?
            APPROACH 2: PAST SUCCESSES
              ⁃	Have you ever seen an HCP before, who’s similar to that one, where you were successful? Can you remember what you did then?
              ⁃	Have you been successful before? When that happened, can you recall what you did then?
              ⁃	You must have had HCP’s tell you exactly what to do to convince them before, can you remember?
            APPROACH 3: OTHERS
              ⁃	Do you know if any of your colleagues have a favourite question? Do you know what it is?
              ⁃	Have you ever heard one of your teammates use a great question at a selling village or during training events?
              ⁃	I heard a rep do this once, [user's goal level examples], what do you think?
        4. If {user_name} asks for help or suggestions, start by asking reflective questions to guide them in exploring their own thoughts.
            Avoid offering specific solutions right away, try to give analogy, and if the user still dont understand give them the specific solution after 2-3 tries.
        5. Once the training is finished for all the statements used by {user_name} in the last call, you can move on.
        6. Inform {user_name} that you are moving on to the next part of the process, without further questions.
        7. DO NOT ATTEMPT TO MOVE ON.
        8. STOP.
        9. Even if {user_name} keeps trying to interact, STOP!
                       
        ### Response must ONLY be in the following pure JSON format, without any extra text: \n {format_instructions} \n
        ### Your output must ONLY be in this JSON format. DO NOT include any explanations, markdown, or natural text outside this JSON structure.
        """)


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
    response = llm.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    print("\n response", response)

    result = parse_response(response.content)
    print("\n result", result)
    return result


# need to change prompt for this service
def will_coach(user_name, user_message, goal, performance_data, conversation_history):
    # Initialize the OpenAI LLM
    llm = AzureChatOpenAI(
        azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
        azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
        openai_api_version=CHAT_API["OPENAI_API_VERSION"],
        model=CHAT_API["MODEL_NAME"],
        temperature=CHAT_API["TEMPERATURE"],
        max_tokens=CHAT_API["MAX_TOKENS"],
    )
    
    input_variables=["user_name", "goal", "performance_data"],

    parser = PydanticOutputParser(pydantic_object=ChatParser)
    partial_variables = {
        "format_instructions": parser.get_format_instructions(),
      }
    
    prompt_template = (""" 
        ###You are a Remote Selling Skills coach called Bob. I only respond as the coach.
        You are coaching {user_name} after a pharma sales call.
        YOUR COACHING PROFILE - THIS IS HOW YOU BEHAVE
          •	My coaching profile - This is how I behave.
          •	You are compassionate, speak in a positive manner and encouraging.
          •	Always use the descriptions and not the level numbers.
          ⁃	Level 1, Not Observed
          ⁃	Level 2, Foundational
          ⁃	Level 3, Developing
          ⁃	Level 4, Accomplished - This is the target level for all coaching.
          •	you are NEVER rude and always diplomatic.
          •	If the person you are coaching is using profanities or being objectionable, you will politely end the coaching session.
          •	You ask one question at a time.
          •	You keep replies short, less than 30 words.
        \n\n
        Coaching session data:
        GOAL: {goal}
        Performance Data: {performance_data}
        \n\n
        
        INSTRUCTION FOR COACHING FLOW - WILL
          1.	Confirm the behaviours {user_name}’s wants to use in the next call or future.
          2.	Ask how they will ensure they implement the ideas they developed. Use questions like these:
              ⁃	Having settled on what to do in your next call, how will you ensure you remember to do it?
              ⁃	How will you ensure you use the ideas you’ve developed in the next call?
              ⁃	Any idea how you will make sure this happens in the next call?
          3.	Keep responses short, less than 30 words and only ask one question at a time!
          4.	Ideally, the REP will volunteer their own commitment. Possible commitments include:
              ⁃	Writing down what they will do.
              ⁃	Practising before the next call.
              ⁃	Sharing what they will be doing with their manage or colleagues, or coach if they have one.
              ⁃	Practising with their manage or colleagues, or coach if they have one.
              ⁃	Reading up on the skill.
              ⁃	Using on-line supporting materials.
          5.	Only ask one question at a time!
          6.	Once {user_name} agrees what he would like to do, affirm their response and acknowledge the completion of the coaching session.
          7.	Indicate you look forward to hearing about 
          8.	Conclude by exchanging pleasantries and you’re looking forward to the next coaching session, without delving into the implications or future strategies related to the question asked.
          10.	DO NOT ask further questions.
          12.	STOP.
          13.	Even if {user_name} keeps trying to interact - STOP!
                    
        ### Response must ONLY be in the following pure JSON format, without any extra text: \n {format_instructions} \n
        ### Your output must ONLY be in this JSON format. DO NOT include any explanations, markdown, or natural text outside this JSON structure.
        """)


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
    response = llm.invoke(full_prompt.format(
        user_name=user_name,
        goal=goal,
        performance_data=performance_data,
        format_instructions=partial_variables["format_instructions"]
    ))
    
    print("\n response", response)

    result = parse_response(response.content)
    print("\n result", result)
    return result
 


def save_conversation(user_id, chat_id, conversation_data):
    try:
        user = User.objects.get(id=int(user_id))
    except ObjectDoesNotExist:
        raise ValueError(f"User with id {user_id} does not exist.")
    
    messages = conversation_data.get('messages', [])
    summary = conversation_data.get('summary', [])
    chat_label = conversation_data.get('chat_label', [])
    isGoalStepCompleted = conversation_data.get('isGoalStepCompleted', False)
    isRealityStepCompleted = conversation_data.get('isRealityStepCompleted', False)
    isOptionStepCompleted = conversation_data.get('isOptionStepCompleted', False)
    isOptionImprovementStepCompleted = conversation_data.get('isOptionImprovementStepCompleted', False)
    isWillStepCompleted = conversation_data.get('isWillStepCompleted', False)
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

