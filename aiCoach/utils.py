import json
import re
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

from aiCoach.models import UserConversationHistory, User

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

# Initialize the OpenAI LLM Model
LLM_MODEL = AzureChatOpenAI(
    azure_deployment=CHAT_API["MODEL_DEPLOYMENT"],
    azure_endpoint=CHAT_API["OPENAI_ENDPOINT"],
    openai_api_version=CHAT_API["OPENAI_API_VERSION"],
    model=CHAT_API["MODEL_NAME"],
    temperature=CHAT_API["TEMPERATURE"],
    max_tokens=CHAT_API["MAX_TOKENS"],
)

def parse_response(response):
    json_data = response
    print("\n json_data", json_data)

    # Extract JSON code block if present
    if "```json" in response:
        json_match = re.findall(r"```json(.*?)```", response, re.DOTALL)
        if json_match:
            json_data = json.loads(json_match[0].strip())
            # print("Extracted JSON:", json_data)

    # Extract other code block if present
    elif "```" in response:
        code_match = re.findall(r"```(.*?)```", response, re.DOTALL)
        if code_match:
            # print("Extracted Code:", code_match[0].strip())
            return code_match[0].strip()

    # Attempt to parse the response as JSON if no code block was found
    try:
        if type(response) is str:
            json_data = json.loads(response.strip())
    except json.JSONDecodeError:
        print("Response is not valid JSON.")

    return json_data