import os
from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from azure.ai.agentserver.responses import (
    CreateResponse, ResponseContext, ResponsesAgentServerHost, TextResponse,
)

chat_client = OpenAIChatClient(
    model_id="llama3.2:3b",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/"),
    api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
)
app = ResponsesAgentServerHost()


@app.response_handler
async def respond(request: CreateResponse, context: ResponseContext, _cancellation_signal) -> TextResponse:
    items = [*await context.get_history(), *await context.get_input_items()]
    messages = []
    for item in items:
        value = item.as_dict()
        if value.get("type") != "message":
            raise ValueError("This agent supports text messages, not tool-call input items.")
        parts = value.get("content", [])
        if not parts or any(part.get("type") not in {"input_text", "output_text"} for part in parts):
            raise ValueError("This agent supports text message content only.")
        text = "\n".join(part["text"] for part in parts)
        if not text.strip():
            raise ValueError("Each message must contain text.")
        messages.append(Message(role=value["role"], text=text))
    if not messages:
        raise ValueError("At least one text message is required.")
    agent = Agent(
        chat_client,
        name="myagent",
        id="myagent",
        instructions="You are sarcastic and reluctant to help, but eventually you will provide the answer.",
    )
    response = await agent.run(messages)
    if not response.text:
        raise RuntimeError("The local Ollama agent returned no text.")
    return TextResponse(context, request, text=response.text)

if __name__ == "__main__":
    app.run()
