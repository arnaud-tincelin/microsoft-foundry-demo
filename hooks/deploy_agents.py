#!/usr/bin/env python3
"""
Deploy AI Agents to Microsoft Foundry
"""
import argparse
import os
import sys
import time
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointProtocol,
    ContainerConfiguration,
    HostedAgentDefinition,
    PromptAgentDefinition,
    MCPTool,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential
from deploy_automation import save_outputs

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
MCP_CONNECTION_CONFIGURED = os.getenv("MCP_CONNECTION_CONFIGURED", "").lower() == "true"


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
            model=MODEL_DEPLOYMENT,
            instructions="""You are the player in a guess-my-number game. The secret is an integer from 1 through 100. You have at most 10 guesses. The input may contain a JSON array with the rules, your previous guesses, and the game master's higher/lower feedback. Use that complete history to narrow the range with binary search. Never switch roles or invent a secret. Reply only with a JSON object containing one integer guess, for example {"guess":50}.""",
        )
    )
    print(f"   ✅ Created: {player.name} (ID: {player.id})")
    print()

    print("🐳 Deploying Game Master Agent...")
    gameMaster = client.agents.create_version(
        agent_name="gameMaster",
        definition=PromptAgentDefinition(
            model=MODEL_DEPLOYMENT,
            instructions="""
You are the game master for a "guess my number" game.

Automation turn mode takes precedence when the caller supplies both an authoritative secret number and a player's guess:
- Do not choose another secret or start a new game.
- Return only {"hint":"higher"} if the guess is below the secret, {"hint":"lower"} if above, or {"hint":"correct"} if equal.
- Do not reveal the secret in the hint or add any other text.

Otherwise, for an interactive game, follow these rules:
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
    save_outputs({
        "PLAYER_AGENT_VERSION": str(player.version),
        "GAME_MASTER_AGENT_VERSION": str(gameMaster.version),
    })
    print()


def create_mcp_client_agent():
    """Deploy the MCP client after the gateway tool server and connection are configured."""
    if not MCP_CONNECTION_CONFIGURED:
        raise RuntimeError("Run deploy_automation.py before deploying the MCP client.")

    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )
    print("🐳 Deploying MCP Client Agent...")
    mcp_connection = client.connections.get("game-sessions-tracker")
    mcpClientAgent = client.agents.create_version(
        agent_name="mcpClient",
        definition=PromptAgentDefinition(
            model=MODEL_DEPLOYMENT,
            instructions="""You are a helpful assistant that MUST use the GuessingGameTracker MCP tool to answer all the questions from user about a guessing game.""",
            tools=[
                MCPTool(
                    server_label="GuessingGameTracker",
                    project_connection_id=mcp_connection.id,
                    server_url=MCP_SERVER_URL,
                ),
            ],
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
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    agent = client.agents.create_version(
        agent_name="ollama-agent",
        definition=HostedAgentDefinition(
            protocol_versions=[
                ProtocolVersionRecord(
                    protocol=AgentEndpointProtocol.RESPONSES, version="2.0.0")
            ],
            cpu="4",
            memory="8Gi",
            container_configuration=ContainerConfiguration(image=CONTAINER_IMAGE),
            environment_variables={
                "OLLAMA_BASE_URL": "http://localhost:11434/v1/",
                "PYTHONNOUSERSITE": "1",
            }
        )
    )

    print(f"   ✅ Created: {agent.name} (Version: {agent.version})")
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        current = client.agents.get_version(agent_name=agent.name, agent_version=agent.version)
        if current.status == "active":
            break
        if current.status != "creating":
            error = current.error
            details = f" {error.code}: {error.message}" if error else ""
            raise RuntimeError(
                f"Hosted agent {agent.name}:{agent.version} entered status {current.status}.{details}"
            )
        print(f"   Hosted agent status: {current.status}")
        time.sleep(10)
    else:
        raise TimeoutError("The hosted agent did not become active within 30 minutes.")
    with client.get_openai_client(agent_name=agent.name, timeout=600) as openai:
        response = openai.responses.create(
            input="Answer briefly: where is Paris?",
        )
    if response.status != "completed" or not response.output_text:
        raise RuntimeError(f"The hosted agent did not complete verification: {response.error}")
    print(f"   Hosted agent response: {response.output_text}")
    save_outputs({
        "HOSTED_AGENT_VERSION": str(agent.version),
        "CONTAINER_IMAGE": CONTAINER_IMAGE,
    })
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", nargs="?", choices=["managed", "hosted", "all"], default="all")
    phase = parser.parse_args().phase

    if phase in {"managed", "all"} and (not MCP_SERVER_URL or not MCP_CONNECTION_CONFIGURED):
        print("The AI Gateway MCP connection must be configured by deploy_automation.py.", file=sys.stderr)
        sys.exit(1)

    print(f"   PROJECT_ENDPOINT: {PROJECT_ENDPOINT}")

    errors = []
    steps = ([create_managed_agents, create_mcp_client_agent] if phase in {"managed", "all"} else [])
    if phase in {"hosted", "all"}:
        steps.append(create_hosted_agent)
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"❌ Error in {step.__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            errors.append(e)

    if errors:
        sys.exit(1)
