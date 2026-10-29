import contextlib
import io
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import run_workflow


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.test/workflows/game/invoke?sig=private-signature"
        self.result = {
            "conversation_id": "conv-123",
            "number_picked": 42,
            "status": "won",
            "turns": 6,
            "message": {"status": "won", "number": 42},
            "session": {"session_id": "session-123"},
        }

    def response(self, result, status=200):
        response = io.BytesIO(json.dumps(result).encode())
        response.status = status
        return response

    @patch.object(run_workflow, "urlopen")
    def test_posts_to_automation_once_and_does_not_record_twice(self, urlopen):
        urlopen.return_value = self.response(self.result)
        self.assertEqual(run_workflow.run_workflow(self.url), self.result)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, self.url)
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {})
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertNotIn("Ocp-apim-subscription-key", request.headers)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 360)

    def test_accepts_early_win_final_turn_win_and_full_length_loss(self):
        for status, turns in (("won", 1), ("won", 10), ("lost", 10)):
            with self.subTest(status=status, turns=turns):
                result = dict(
                    self.result, status=status, turns=turns,
                    message={"status": status, "number": 42 if status == "won" else "-1"},
                )
                self.assertEqual(run_workflow.validate_result(result), result)

    def test_accepts_conversation_trace_and_agent_metadata(self):
        result = dict(
            self.result, game_run_id="run-123", trace_id="trace-123",
            agent_versions={"player": "5", "game_master": "19"},
        )
        self.assertEqual(run_workflow.validate_result(result), result)

    def test_rejects_invalid_results(self):
        invalid = [
            None, [], {}, dict(self.result, status="unknown"),
            dict(self.result, number_picked=-1),
            dict(self.result, number_picked=0),
            dict(self.result, number_picked=101),
            dict(self.result, number_picked="42"),
            dict(self.result, number_picked=True),
            dict(self.result, turns=0),
            dict(self.result, turns=11),
            dict(self.result, turns=True),
            dict(self.result, status="lost", turns=9),
            dict(self.result, message=None),
            dict(self.result, message={"status": "won"}),
            dict(self.result, message={"status": "lost", "number": "-1"}),
            dict(self.result, message={"status": "won", "number": 41}),
            dict(self.result, message={"status": "won", "number": "42"}),
            dict(self.result, number_picked=1, message={"status": "won", "number": True}),
            dict(self.result, status="lost", turns=10, message={"status": "lost", "number": -1}),
            dict(self.result, conversation_id=""),
            dict(self.result, conversation_id=123),
            dict(self.result, session=None),
            dict(self.result, session={"session_id": ""}),
        ]
        for result in invalid:
            with self.subTest(result=result), self.assertRaises(ValueError):
                run_workflow.validate_result(result)

    @patch.object(run_workflow, "urlopen")
    def test_rejects_bad_callback_url_before_sending(self, urlopen):
        for url in ("", "http://example.test", "https:///path", "https://user:pass@example.test", self.url + "#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                run_workflow.run_workflow(url)
        urlopen.assert_not_called()

    @patch.object(run_workflow, "urlopen")
    def test_rejects_async_acknowledgement_as_completed_game(self, urlopen):
        urlopen.return_value = self.response({}, status=202)
        with self.assertRaisesRegex(ValueError, "not a completed game"):
            run_workflow.run_workflow(self.url)

    @patch.object(run_workflow, "urlopen")
    def test_rejects_malformed_json(self, urlopen):
        response = io.BytesIO(b"not JSON")
        response.status = 200
        urlopen.return_value = response
        with self.assertRaises(ValueError):
            run_workflow.run_workflow(self.url)

    @patch.object(run_workflow, "urlopen")
    def test_transport_errors_do_not_expose_callback_signature(self, urlopen):
        errors = [
            HTTPError(self.url, 502, "private-signature", {}, None),
            URLError(self.url), TimeoutError(self.url),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                urlopen.side_effect = error
                with self.assertRaises(RuntimeError) as raised:
                    run_workflow.run_workflow(self.url)
                self.assertNotIn("private-signature", str(raised.exception))

    def test_missing_configuration_exits_nonzero(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(run_workflow.main(), 1)
        self.assertIn("LOGIC_APPS_WORKFLOW_URL", stderr.getvalue())

    @patch.object(run_workflow, "urlopen")
    def test_http_failure_exits_nonzero_without_leaking_url(self, urlopen):
        urlopen.side_effect = HTTPError(self.url, 401, "Unauthorized", {}, None)
        with patch.dict(os.environ, {"LOGIC_APPS_WORKFLOW_URL": self.url}), contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(run_workflow.main(), 1)
        self.assertIn("HTTP 401", stderr.getvalue())
        self.assertNotIn("private-signature", stderr.getvalue())


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = json.loads(Path(__file__).with_name("workflow.json").read_text())
        cls.definition = cls.workflow["definition"]
        cls.actions = cls.definition["actions"]
        cls.loop = cls.actions["Play_up_to_ten_turns"]
        cls.turn = cls.loop["actions"]

    def test_stateful_http_workflow_has_bounded_loop(self):
        self.assertEqual(self.workflow["kind"], "Stateful")
        trigger = next(iter(self.definition["triggers"].values()))
        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["inputs"]["method"], "POST")
        self.assertEqual(self.loop["type"], "Until")
        self.assertEqual(self.loop["limit"], {"count": 10, "timeout": "PT5M"})
        self.assertNotIn("operationOptions", self.loop)
        self.assertEqual(self.loop["runAfter"], {"Create_conversation": ["Succeeded"]})
        self.assertIn("not(equals(body('Player')['status'], 'completed'))", self.loop["expression"])
        self.assertIn("not(equals(body('Game_master')['status'], 'completed'))", self.loop["expression"])
        self.assertIn("['status'], 'playing'))", self.loop["expression"])

    def test_only_two_agents_run_inside_loop_and_no_memory_scaffolding_remains(self):
        self.assertEqual(list(self.turn), ["Player", "Game_master"])
        self.assertNotIn("runAfter", self.turn["Player"])
        self.assertEqual(self.turn["Game_master"]["runAfter"], {"Player": ["Succeeded"]})
        self.assertEqual(set(self.actions), {
            "Create_conversation", "Play_up_to_ten_turns", "Game_result", "Record_session",
            "Respond_with_result", "Respond_with_error", "Fail_run",
        })
        encoded = json.dumps(self.definition)
        for removed in ("Remember_", "Read_", "Filter_", "variables(", "Turn_result", '"type": "Workflow"'):
            self.assertNotIn(removed, encoded)

    def test_both_version_pinned_agents_reuse_exactly_one_conversation(self):
        create = self.actions["Create_conversation"]["inputs"]
        self.assertEqual(create["uri"],
                         "@concat(parameters('foundryProjectEndpoint'), '/openai/v1/conversations')")
        self.assertEqual(create["body"]["items"][0]["role"], "user")
        self.assertIn("player moves first", create["body"]["items"][0]["content"])
        for name, agent, parameter in (
            ("Player", "player", "playerAgentVersion"),
            ("Game_master", "gameMaster", "gameMasterAgentVersion"),
        ):
            action = self.turn[name]
            inputs = action["inputs"]
            self.assertEqual(action["type"], "Http")
            self.assertEqual(inputs["method"], "POST")
            self.assertEqual(inputs["uri"],
                             "@concat(parameters('foundryProjectEndpoint'), '/openai/v1/responses')")
            self.assertEqual(inputs["body"]["conversation"], "@body('Create_conversation')['id']")
            self.assertEqual(inputs["body"]["agent_reference"], {
                "type": "agent_reference", "name": agent,
                "version": f"@parameters('{parameter}')",
            })
            self.assertNotIn("text", inputs["body"])
        self.assertNotIn("number_picked", json.dumps(self.turn))
        self.assertIn("latest player guess", self.turn["Game_master"]["inputs"]["body"]["input"])

    def test_foundry_uses_managed_identity_no_retries_and_shared_trace(self):
        for action in (self.actions["Create_conversation"], *self.turn.values()):
            inputs = action["inputs"]
            self.assertEqual(inputs["authentication"], {
                "type": "ManagedServiceIdentity", "audience": "https://ai.azure.com",
            })
            self.assertEqual(inputs["retryPolicy"], {"type": "none"})
        for action in self.turn.values():
            self.assertEqual(action["runtimeConfiguration"]["secureData"], {
                "properties": ["inputs", "outputs"],
            })
            self.assertIn("body('Create_conversation')['metadata']['trace_id']",
                          action["inputs"]["headers"]["traceparent"])
            self.assertEqual(action["inputs"]["body"]["metadata"]["turn"],
                             "@string(add(iterationIndexes('Play_up_to_ten_turns'), 1))")

    def test_final_result_parses_last_reply_and_validates_completion_before_recording(self):
        result = self.actions["Game_result"]
        self.assertEqual(result["type"], "ParseJson")
        self.assertEqual(result["runAfter"], {"Play_up_to_ten_turns": ["Succeeded"]})
        content = result["inputs"]["content"]
        self.assertEqual(content["status"],
                         "@json(last(last(body('Game_master')['output'])['content'])['text'])['status']")
        self.assertEqual(content["turns"], "@int(body('Game_master')['metadata']['turn'])")
        self.assertEqual(content["conversation_id"], "@body('Create_conversation')['id']")
        self.assertIn("equals(body('Player')['status'], 'completed')", content["valid"])
        self.assertIn("equals(body('Game_master')['status'], 'completed')", content["valid"])
        self.assertIn("body('Player')['conversation']['id']", content["valid"])
        self.assertIn("body('Game_master')['conversation']['id']", content["valid"])
        schema = result["inputs"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(content))
        self.assertEqual(schema["properties"]["valid"], {"type": "boolean", "enum": [True]})
        self.assertEqual(schema["properties"]["number_picked"],
                         {"type": "integer", "minimum": 1, "maximum": 100})
        self.assertIn("'won', 'lost'", schema["properties"]["status"]["enum"])
        self.assertIn("'lost'), createArray(10), range(1, 10)", schema["properties"]["turns"]["enum"])

    def test_records_actual_conversation_once_before_success_response(self):
        record = self.actions["Record_session"]
        self.assertEqual(record["runAfter"], {"Game_result": ["Succeeded"]})
        self.assertEqual(record["inputs"]["body"], {
            name: f"@body('Game_result')['{name}']"
            for name in ("conversation_id", "number_picked", "status")
        })
        self.assertEqual(record["inputs"]["retryPolicy"], {"type": "none"})
        response = self.actions["Respond_with_result"]
        self.assertEqual(response["runAfter"], {"Record_session": ["Succeeded"]})
        body = response["inputs"]["body"]
        self.assertEqual(body["session"], "@body('Record_session')")
        self.assertEqual(body["turns"], "@body('Game_result')['turns']")
        self.assertEqual(body["message"], {
            "status": "@body('Game_result')['status']",
            "number": "@if(equals(body('Game_result')['status'], 'won'), body('Game_result')['number_picked'], '-1')",
        })
        self.assertEqual(self.actions["Respond_with_error"]["inputs"]["statusCode"], 502)
        self.assertEqual(self.actions["Respond_with_error"]["runAfter"],
                         {"Record_session": ["Failed", "Skipped", "TimedOut"]})
        self.assertEqual(self.actions["Fail_run"]["inputs"]["runStatus"], "Failed")

    def test_all_action_and_parameter_references_resolve_without_unused_parameters(self):
        all_actions = {**self.actions, **self.turn}
        for actions in (self.actions, self.turn):
            for action in actions.values():
                for dependency in action.get("runAfter", {}):
                    self.assertIn(dependency, actions)
        encoded = json.dumps(self.definition)
        references = re.findall(r"(?:body|outputs|actions|iterationIndexes)\('([^']+)'\)", encoded)
        self.assertTrue(set(references) <= set(all_actions))
        parameters = set(re.findall(r"parameters\('([^']+)'\)", encoded))
        self.assertEqual(parameters, set(self.definition["parameters"]))
        self.assertEqual(len(all_actions), 9)


if __name__ == "__main__":
    unittest.main()
