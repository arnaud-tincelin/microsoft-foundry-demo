import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from starlette.testclient import TestClient

import hostedAgent


class HostedProtocolTests(unittest.IsolatedAsyncioTestCase):
    def item(self, role, text, part_type="input_text"):
        item = Mock()
        item.as_dict.return_value = {
            "type": "message", "role": role,
            "content": [{"type": part_type, "text": text}],
        }
        return item

    def context(self, inputs, history=()):
        return SimpleNamespace(
            get_input_items=AsyncMock(return_value=inputs),
            get_history=AsyncMock(return_value=history),
        )

    async def test_preserves_history_roles_and_returns_a_protocol_text_response(self):
        context = self.context([self.item("user", "And its country?")], [
            self.item("user", "Where is Paris?"),
            self.item("assistant", "Paris is in France.", "output_text"),
        ])
        agent = Mock()
        agent.run = AsyncMock(return_value=SimpleNamespace(text="France."))
        request = Mock()
        with patch("hostedAgent.Agent", return_value=agent), patch("hostedAgent.TextResponse") as response:
            await hostedAgent.respond(request, context, None)
        messages = agent.run.call_args.args[0]
        self.assertEqual([message.role for message in messages], ["user", "assistant", "user"])
        self.assertEqual([message.text for message in messages], [
            "Where is Paris?", "Paris is in France.", "And its country?",
        ])
        response.assert_called_once_with(context, request, text="France.")

    async def test_rejects_empty_or_non_text_input_explicitly(self):
        tool = Mock()
        tool.as_dict.return_value = {"type": "function_call_output"}
        for inputs in [[], [self.item("user", "")], [self.item("user", "image", "input_image")], [tool]]:
            with self.subTest(inputs=inputs), patch("hostedAgent.Agent") as agent:
                with self.assertRaises(ValueError):
                    await hostedAgent.respond(Mock(), self.context(inputs), None)
            agent.assert_not_called()

    async def test_does_not_hide_ollama_failures_or_empty_responses(self):
        agent = Mock()
        agent.run = AsyncMock(side_effect=RuntimeError("Ollama unavailable"))
        with patch("hostedAgent.Agent", return_value=agent):
            with self.assertRaisesRegex(RuntimeError, "Ollama unavailable"):
                await hostedAgent.respond(Mock(), self.context([self.item("user", "Hello")]), None)
        agent.run = AsyncMock(return_value=SimpleNamespace(text=""))
        with patch("hostedAgent.Agent", return_value=agent):
            with self.assertRaisesRegex(RuntimeError, "returned no text"):
                await hostedAgent.respond(Mock(), self.context([self.item("user", "Hello")]), None)

    async def test_http_protocol_persists_history_and_supports_streaming(self):
        agent = Mock()
        agent.run = AsyncMock(return_value=SimpleNamespace(text="Paris is in France."))
        with patch("hostedAgent.Agent", return_value=agent), TestClient(hostedAgent.app) as client:
            response = client.post("/responses", json={"input": "Where is Paris?", "stream": False})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["status"], "completed")
            self.assertEqual(body["output"][0]["content"][0]["text"], "Paris is in France.")

            response = client.post("/responses", json={
                "input": "And its country?", "previous_response_id": body["id"], "stream": False,
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "completed")
            messages = agent.run.call_args.args[0]
            self.assertEqual([message.text for message in messages], [
                "Where is Paris?", "Paris is in France.", "And its country?",
            ])

            response = client.post("/responses", json={"input": "Say hello.", "stream": True})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("text/event-stream", response.headers["Content-Type"])
            events = [
                json.loads(line[6:]) for line in response.text.splitlines()
                if line.startswith("data: ") and line[6:] != "[DONE]"
            ]
            self.assertEqual(events[-1]["type"], "response.completed")


if __name__ == "__main__":
    unittest.main()
