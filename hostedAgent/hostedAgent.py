import asyncio
import os
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from azure.ai.agentserver.agentframework import from_agent_framework

async def main() -> None:
    chat_client = OpenAIChatClient(
        model_id="llama3.2:3b",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    )
    agent = Agent(chat_client,
                  name = "myagent",
                  id = "myagent",
                  instructions="You are sarcastic and reluctant to help, but eventually you will provide the answer.")

    # Use the agent server adapter to host the agent
    # This automatically creates a REST API on port 8088 with /responses endpoint
    await from_agent_framework(agent).run_async()

if __name__ == "__main__":
    asyncio.run(main())
