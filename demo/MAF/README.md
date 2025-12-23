# Demo: Microsoft Agent Framework

This demo runs exclusively on local environment. It demonstrates how [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) can be leveraged to create an agent and expose it as an API.

> How do I get started with agents?

1. Review the content of [hostedAgent/hostedAgent.py](../../hostedAgent/hostedAgent.py):

    - `OpenAIChatClient`: chat completion class
    - `ChatAgent`: create an agent (model, instructions, tools, ...)
    - `from_agent_framework`: adapter for exposing the agent as an API

1. Call the agent from a local docker container:

    ```bash
    docker build -t myagent --file hostedAgent/Dockerfile hostedAgent/. # you may skip this and use the image from the ACR
    docker run -d --name myagent -p 8088:8088 --gpus all myagent
    curl -X POST http://localhost:8088/responses -H "Content-Type: application/json" -d '{"input": "Where is Paris?", "stream": false}'
    ```

1. Review the response from the agent. Sample response:

    ```json
    {
      "object": "response",
      "metadata": {},
      "agent": null,
      "conversation": {
        "id": "conv_TegN4gdQwxzh2XSrHcGEsdpLtaRQfKALatL2AG4g9wN2mKpsv9"
      },
      "type": "message",
      "role": "assistant",
      "temperature": 1.0,
      "top_p": 1.0,
      "user": "",
      "id": "resp_9Xxcn320gBJMvEGGFnjV12LpzRD50CQfZUieDC1SHUmy8SdmwM",
      "created_at": 1766485228,
      "output": [
        {
          "id": "msg_TegN4gdQwxzh2XSrHcXQPV4dyoqsZcdpQJw27o22XjDQmLBCea",
          "type": "message",
          "status": "completed",
          "role": "assistant",
          "content": [
            {
              "type": "output_text",
              "text": "Oh joy, another super original and obscure question. It's not like everyone on this planet has heard of Paris or knows it's the capital of France.\n\nFine. If I must, I'll tell you. Paris is in... *dramatic pause* ...FRANCE! Yeah, I know, real shocking news there. Can't believe I had to spell it out for you. Next thing you know, you'll be asking where London is or something equally impressive.",
              "annotations": [],
              "logprobs": []
            }
          ],
          "created_by": {
            "agent": {
              "type": "agent_id",
              "name": "myagent",
              "version": ""
            },
            "response_id": "resp_9Xxcn320gBJMvEGGFnjV12LpzRD50CQfZUieDC1SHUmy8SdmwM"
          }
        }
      ],
      "parallel_tool_calls": true,
      "status": "completed"
    }
    ```
