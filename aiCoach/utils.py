import json
import re

def parse_response(response):
    json_data = response

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