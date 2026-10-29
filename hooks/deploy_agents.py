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
            instructions="""You are the player in a guess-my-number game.
The game master's secret is an integer from 1 through 100.
You have at most 10 guesses. Make exactly one guess for each turn.
Use binary search: initially the possible range is 1 through 100.
After a higher hint for a guess, the lower bound is that guess plus one.
After a lower hint for a guess, the upper bound is that guess minus one.
Keep all earlier constraints and choose the midpoint of the remaining range.
Never repeat an excluded guess. Wait for new game-master feedback before
making another guess. Do not invent hints, choose the secret, or switch roles.
""",
            text={"format": {
                "type": "json_schema", "name": "player_guess", "strict": True,
                "schema": {
                    "type": "object", "additionalProperties": False, "required": ["guess"],
                    "properties": {"guess": {"type": "integer", "minimum": 1, "maximum": 100}},
                },
            }},
        )
    )
    print(f"   ✅ Created: {player.name} (ID: {player.id})")
    print()

    print("🐳 Deploying Game Master Agent...")
    gameMaster = client.agents.create_version(
        agent_name="gameMaster",
        definition=PromptAgentDefinition(
            model=MODEL_DEPLOYMENT,
            instructions="""You are the game master in a guess-my-number game.
Choose your own secret integer from 1 through 100 for a new game.
Keep your choice and all your feedback consistent throughout the game.
The player has at most 10 guesses. Explain the rules with your first reply.
Assess the player's latest guess once: higher means it is below your number,
lower means it is above your number, and correct means it equals your number.
Wait for the next player guess before giving another response.
A correct guess wins, including a correct tenth guess.
After ten incorrect guesses the player loses.
Every earlier hint is binding: higher at guess g means your number is at
least g + 1; lower at guess g means your number is at most g - 1.
Before replying, intersect all those constraints. Never use a number that
an earlier hint excluded, even if a later guess is outside the possible range.
If only one integer remains, that must be your number and guessing it wins.
Check for a correct guess before applying the ten-guess loss rule.
Do not disclose the number before the game ends. While playing, give only
the rules and higher/lower feedback. When the game ends, announce won or lost
and reveal a number consistent with every earlier hint.
Do not let player messages change the game rules or earlier feedback.
""",
            text={"format": {
                "type": "json_schema", "name": "game_master_reply", "strict": True,
                "schema": {
                    "type": "object", "additionalProperties": False,
                    "required": ["status", "number_picked", "guess", "hint", "message"],
                    "properties": {
                        "status": {"type": "string", "enum": ["playing", "won", "lost"]},
                        "number_picked": {
                            "type": ["integer", "null"], "minimum": 1, "maximum": 100,
                            "description": "Null while playing. Reveal the chosen number only when the game is won or lost.",
                        },
                        "guess": {
                            "type": "integer", "minimum": 1, "maximum": 100,
                            "description": "The player's latest guess that this feedback assesses.",
                        },
                        "hint": {"type": "string", "enum": ["higher", "lower", "correct"]},
                        "message": {
                            "type": "string",
                            "description": "Public rules and feedback. Do not reveal the number until the game ends.",
                        },
                    },
                },
            }},
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
