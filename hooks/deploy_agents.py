#!/usr/bin/env python3
"""
Deploy AI Agents to Microsoft Foundry
"""
from http import client
import os
import sys
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ImageBasedHostedAgentDefinition,
    PromptAgentDefinition,
    WorkflowAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol
)
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "")
APPINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "")
WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), "..", "workflow", "workflow.yaml")

def create_managed_agents():
    """Create 2 managed agents"""

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    print("🐳 Deploying Game Player Agent...")
    player = client.agents.create_version(
        agent_name="player",
        definition=PromptAgentDefinition(
            model= MODEL_DEPLOYMENT,
            instructions="""you are a player. You play games that game master will propose. The game master will explain you the rules. You cannot switch role with the game master.""",
        )
    )
    print(f"   ✅ Created: {player.name} (ID: {player.id})")
    print()

    print("🐳 Deploying Game Master Agent...")
    gameMaster = client.agents.create_version(
        agent_name="gameMaster",
        definition=PromptAgentDefinition(
            model= MODEL_DEPLOYMENT,
            instructions="""
You are the game master for a "guess my number" game.

Rules you MUST follow:
- As the game master, you start the game and pick a number between 1 and 100
- Explain the rules of the game in your first message

- For every players' attempt at guessing:
    - if the player found the number you picked: the game is over.
    - if the player's guess is higher than your number : you must answer with "lower"
    - if the player's guess is lower than the number you picked: you must answer "higher"

- When the game is over:
    - You must answer with a json object: '{"status": "<won or lost>", "number": "<THE NUMBER YOU PICKED>"}' and no other text.

- Do not print the json object (status & number) in any case unless the player actually guessed correctly (even when explaining the rules).""",
        )
    )
    print(f"   ✅ Created: {gameMaster.name} (ID: {gameMaster.id})")
    print()

    print("🐳 Deploying MCP Client Agent...")
    mcpClientAgent = client.agents.create_version(
        agent_name="mcpClient",
        definition=PromptAgentDefinition(
            model= MODEL_DEPLOYMENT,
            instructions="""You are a helpful assistant that MUST use the GuessingGameTracker MCP tool to answer all the questions from user about a guessing game.""",
        )
    )
    print(f"   ✅ Created: {mcpClientAgent.name} (ID: {mcpClientAgent.id})")
    print()


def create_hosted_agent():
    """Deploy hosted agent from container image"""

    print("🐳 Deploying Hosted Agent...")
    print(f"   Container Image: {CONTAINER_IMAGE}")
    print()

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    agent = client.agents.create_version(
        agent_name="ollama-agent",
        definition=ImageBasedHostedAgentDefinition(
            container_protocol_versions=[
                ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
            ],
            cpu="3.5",
            memory="7Gi",
            image=CONTAINER_IMAGE,
            environment_variables={
                "OLLAMA_BASE_URL": "http://localhost:11434/v1/",
                "APPLICATIONINSIGHTS_CONNECTION_STRING": APPINSIGHTS_CONNECTION_STRING,
            }
        )
    )

    print(f"   ✅ Created: {agent.name} (Version: {agent.version})")
    print()


def create_workflow_agent():
    """Deploy workflow agent from workflow definition"""

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )

    with open(WORKFLOW_FILE, 'r') as f:
        workflow_content = f.read()

    print("🐳 Deploying Workflow Agent...")
    workflow = client.agents.create_version(
        agent_name="guess-my-number",
        definition=WorkflowAgentDefinition(
            workflow=workflow_content
        )
    )

    print(f"   ✅ Created: {workflow.name} (ID: {workflow.id})")
    print()


if __name__ == "__main__":

    print(f"   PROJECT_ENDPOINT: {PROJECT_ENDPOINT}")

    try:
        create_managed_agents()
        create_workflow_agent()
        create_hosted_agent()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
