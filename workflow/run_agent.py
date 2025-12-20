# Before running the sample:
#    pip install --pre azure-ai-projects>=2.0.0b1
#    pip install azure-identity

import os
import json
import requests
from dotenv import load_dotenv, dotenv_values
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ResponseStreamEventType

load_dotenv()
project_endpoint = os.getenv("PROJECT_ENDPOINT", "")

print(f"🚀 Starting Guess My Number Agent Workflow @ {project_endpoint}")

project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:

    workflow = {
        "name": "guess-my-number",
        "version": "1",
    }

    openai_client = project_client.get_openai_client()

    conversation = openai_client.conversations.create()

    stream = openai_client.responses.create(
        conversation=conversation.id,
        extra_body={"agent": {"name": workflow["name"], "type": "agent_reference"}},
        input="Hello Agent",
        stream=True,
        metadata={"x-ms-debug-mode-enabled": "1"},
    )

    # Variables to capture workflow outcomes
    workflow_status = "unknown"
    number_picked = 0
    full_output = []
    current_agent = None

    for event in stream:
        if event.type == ResponseStreamEventType.RESPONSE_OUTPUT_ITEM_ADDED and event.item.type == "workflow_action":
            current_agent = event.item.action_id
            print(f"\n[{current_agent}]", end=' ', flush=True)
        elif event.type == ResponseStreamEventType.RESPONSE_OUTPUT_TEXT_DONE:
            full_output.append(event.text)
        elif event.type == ResponseStreamEventType.RESPONSE_OUTPUT_TEXT_DELTA:
            print(event.delta, end='', flush=True)

    print()  # New line after all deltas
    openai_client.conversations.delete(conversation_id=conversation.id)

    # Parse the last message to get the game result
    if full_output:
        try:
            last_message = full_output[-1]
            result = json.loads(last_message)
            workflow_status = result.get("status", "unknown")
            number_picked = result.get("number", 0)
        except json.JSONDecodeError:
            pass

    # Call the game sessions API
    api_url = os.getenv("APIM_API_URL", "") + "/sessions"
    subscription_key = os.getenv("APIM_SUBSCRIPTION_KEY", "")

    payload = {
        "conversation_id": conversation.id,
        "number_picked": number_picked,
        "status": workflow_status
    }

    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"\nAPI Response ({response.status_code}): {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"\nAPI Error: {e}")
