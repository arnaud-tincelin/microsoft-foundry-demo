import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import run_workflow


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.test/workflows/game/invoke?sig=private-signature"
        self.result = {
            "conversation_id": "run-123",
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

    def test_rejects_invalid_results(self):
        invalid = [
            None,
            [],
            {},
            dict(self.result, status="unknown"),
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
            URLError(self.url),
            TimeoutError(self.url),
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
        cls.game = cls.actions["Finalize_game"]["actions"]
        cls.loop = cls.actions["Play_up_to_ten_turns"]
        cls.turn = cls.loop["actions"]
        cls.decision = cls.turn["Check_win_or_turn_limit"]
        cls.turn_limit = cls.decision["else"]["actions"]["Check_turn_limit"]
        cls.continuation = cls.turn_limit["else"]["actions"]
        cls.turn_workflows = {
            name: json.loads(Path(__file__).with_name(name + ".json").read_text())
            for name in ("player-turn", "game-master-turn")
        }

    def test_stateful_http_workflow_has_bounded_loop(self):
        self.assertEqual(self.workflow["kind"], "Stateful")
        trigger = next(iter(self.definition["triggers"].values()))
        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["inputs"]["method"], "POST")
        self.assertEqual(self.loop["type"], "Until")
        self.assertEqual(self.loop["limit"], {"count": 10, "timeout": "PT5M"})
        self.assertEqual(self.loop["operationOptions"], "FailWhenLimitsReached")
        self.assertEqual(
            self.loop["expression"],
            "@or(variables('gameFailed'), not(equals(variables('lastMessage')['status'], 'playing')))",
        )

    def test_turn_is_player_then_master_then_counter_then_decision_without_wrapper_scopes(self):
        self.assertEqual(list(self.turn), [
            "Player", "Game_master", "Count_turn", "Check_win_or_turn_limit", "Mark_failed_turn",
        ])
        self.assertEqual(self.turn["Player"]["runAfter"], {})
        self.assertEqual(self.turn["Game_master"]["runAfter"], {"Player": ["Succeeded"]})
        self.assertEqual(self.turn["Count_turn"]["runAfter"], {"Game_master": ["Succeeded"]})
        self.assertEqual(self.turn["Count_turn"]["type"], "IncrementVariable")
        self.assertEqual(self.turn["Count_turn"]["inputs"], {"name": "turnCount", "value": 1})
        self.assertEqual(self.decision["runAfter"], {"Count_turn": ["Succeeded"]})

    def test_win_is_checked_before_the_tenth_turn_loss(self):
        self.assertEqual(self.decision["type"], "If")
        self.assertEqual(self.decision["expression"], "@equals(body('Game_master')['status'], 'won')")
        self.assertEqual(set(self.decision["actions"]), {"Game_won_message"})
        self.assertEqual(self.decision["actions"]["Game_won_message"]["inputs"], {
            "name": "lastMessage",
            "value": {"status": "won", "number": "@body('Game_master')['number']"},
        })
        self.assertEqual(self.turn_limit["type"], "If")
        self.assertEqual(
            self.turn_limit["expression"], "@greaterOrEquals(variables('turnCount'), 10)",
        )
        self.assertEqual(self.turn_limit["actions"]["Game_lost_message"]["inputs"], {
            "name": "lastMessage", "value": {"status": "lost", "number": "-1"},
        })

    def test_only_the_continue_branch_remembers_the_turn_before_repeating_player(self):
        self.assertEqual(set(self.continuation), {"Remember_guess", "Remember_hint"})
        self.assertEqual(self.continuation["Remember_guess"]["inputs"], {
            "name": "playerMessages",
            "value": {"role": "assistant", "content": "@string(body('Player'))"},
        })
        self.assertEqual(self.continuation["Remember_guess"]["runAfter"], {})
        self.assertEqual(self.continuation["Remember_hint"]["inputs"], {
            "name": "playerMessages",
            "value": {"role": "user", "content": "@body('Game_master')['hint']"},
        })
        self.assertEqual(self.continuation["Remember_hint"]["runAfter"], {
            "Remember_guess": ["Succeeded"],
        })
        self.assertNotIn("lastMessage", json.dumps(self.continuation))
        self.assertNotIn("Terminate", json.dumps(self.turn))

    def test_each_variable_is_initialized_once_at_top_level(self):
        variables = []
        for action in self.actions.values():
            if action["type"] == "InitializeVariable":
                self.assertEqual(len(action["inputs"]["variables"]), 1)
                variables.extend(action["inputs"]["variables"])
        self.assertEqual(len(variables), 5)
        self.assertEqual({value["name"] for value in variables}, {
            "number", "lastMessage", "turnCount", "playerMessages", "gameFailed",
        })
        number = next(value for value in variables if value["name"] == "number")
        self.assertEqual(number["value"], "@rand(1, 101)")
        message = next(value for value in variables if value["name"] == "lastMessage")
        self.assertEqual(message["value"], {"status": "playing"})
        self.assertEqual(set(self.loop["runAfter"]), {
            name for name, action in self.actions.items() if action["type"] == "InitializeVariable"
        })

    def test_native_foundry_agents_use_the_project_connection_and_keep_roles_isolated(self):
        self.assertNotIn("gatewayRuntimeKey", self.definition["parameters"])
        self.assertNotIn("modelBaseUrl", self.definition["parameters"])
        self.assertNotIn('"type": "Agent"', json.dumps(self.definition))
        for name, agent, child, version in (
            ("Player", "player", "player-turn", "playerAgentVersion"),
            ("Game_master", "gameMaster", "game-master-turn", "gameMasterAgentVersion"),
        ):
            invocation = self.turn[name]
            self.assertEqual(invocation["type"], "Workflow")
            self.assertEqual(invocation["inputs"]["host"]["workflow"]["id"], child)
            self.assertEqual(invocation["inputs"]["retryPolicy"]["type"], "none")
            definition = self.turn_workflows[child]["definition"]
            action = definition["actions"]["Foundry_agent"]
            inputs = action["inputs"]
            self.assertEqual(action["type"], "Agent")
            self.assertEqual(inputs["agentModelType"], "FoundryAgentServiceV2")
            self.assertEqual(inputs["modelConfigurations"], {
                "model1": {"referenceName": "foundry-project"},
            })
            self.assertEqual(inputs["parameters"]["foundryAgentId"], agent)
            self.assertEqual(inputs["parameters"]["foundryVersionName"], f"@parameters('{version}')")
            self.assertEqual(action["limit"], {"count": 3, "timeout": "PT1M"})
            self.assertEqual(action["operationOptions"], "FailWhenLimitsReached")
            self.assertEqual(set(action["runtimeConfiguration"]["secureData"]["properties"]), {"inputs", "outputs"})
            self.assertEqual(inputs["retryPolicy"]["type"], "none")
            self.assertNotIn("headers", inputs)
        player = self.turn["Player"]
        self.assertEqual(player["inputs"]["body"], {"messages": "@string(variables('playerMessages'))"})
        child = self.turn_workflows["player-turn"]["definition"]
        self.assertEqual(child["actions"]["Foundry_agent"]["inputs"]["parameters"]["messages"], [
            {"role": "User", "content": "@triggerBody()['messages']"},
        ])
        schema = child["triggers"]["When_an_HTTP_request_is_received"]["inputs"]["schema"]
        self.assertEqual(set(schema["properties"]), {"messages"})
        self.assertFalse(schema["additionalProperties"])
        for name in ("Initialize_player_messages",):
            self.assertNotIn("variables('number')", json.dumps(self.actions[name]))
        for name in ("Remember_guess", "Remember_hint"):
            self.assertNotIn("variables('number')", json.dumps(self.continuation[name]))
        self.assertNotIn("variables('number')", json.dumps(player["inputs"]))
        self.assertIn("variables('number')", json.dumps(self.turn["Game_master"]["inputs"]["body"]))
        self.assertEqual(self.turn["Game_master"]["inputs"]["body"]["guess"], "@body('Player')['guess']")

    def test_guesses_and_hints_are_validated_before_the_turn_completes(self):
        player = self.turn_workflows["player-turn"]["definition"]["actions"]
        master = self.turn_workflows["game-master-turn"]["definition"]["actions"]
        schema = player["Parse_player_guess"]["inputs"]["schema"]["properties"]["guess"]
        self.assertEqual(schema, {"type": "integer", "minimum": 1, "maximum": 100})
        hint = master["Validate_master_hint"]["inputs"]["schema"]["properties"]["hint"]
        self.assertEqual(master["Validate_master_hint"]["runtimeConfiguration"]["secureData"], {
            "properties": ["inputs"],
        })
        self.assertEqual(
            hint["enum"],
            "@createArray(if(equals(triggerBody()['guess'], triggerBody()['number']), 'correct', if(less(triggerBody()['guess'], triggerBody()['number']), 'higher', 'lower')))",
        )
        for actions, validation in ((player, "Parse_player_guess"), (master, "Validate_master_hint")):
            self.assertEqual(
                actions[validation]["inputs"]["content"], "@outputs('Foundry_agent')['lastAssistantMessage']",
            )
            self.assertEqual(actions[validation]["runAfter"], {"Foundry_agent": ["Succeeded"]})
            self.assertEqual(actions["Return_agent_response"]["runAfter"], {validation: ["Succeeded"]})
            self.assertEqual(
                actions["Respond_with_error"]["runAfter"],
                {validation: ["Failed", "Skipped", "TimedOut"]},
            )
            self.assertEqual(actions["Respond_with_error"]["inputs"]["statusCode"], 502)
            self.assertEqual(actions["Fail_run"]["inputs"]["runStatus"], "Failed")
        self.assertEqual(player["Return_agent_response"]["inputs"]["body"], "@body('Parse_player_guess')")
        self.assertEqual(master["Return_agent_response"]["inputs"]["body"], {
            "status": "@if(equals(body('Validate_master_hint')['hint'], 'correct'), 'won', 'playing')",
            "hint": "@body('Validate_master_hint')['hint']",
            "number": "@if(equals(body('Validate_master_hint')['hint'], 'correct'), triggerBody()['number'], -1)",
        })

    def test_result_uses_real_number_and_recording_precedes_success_response(self):
        self.assertEqual(self.actions["Finalize_game"]["runAfter"], {
            "Play_up_to_ten_turns": ["Succeeded"],
        })
        result = self.game["Game_result"]
        self.assertEqual(result["runAfter"], {"Validate_game_completion": ["Succeeded"]})
        self.assertEqual(result["inputs"]["number_picked"], "@variables('number')")
        self.assertEqual(result["inputs"]["status"], "@variables('lastMessage')['status']")
        record = self.game["Record_session"]
        self.assertEqual(record["runAfter"], {"Game_result": ["Succeeded"]})
        self.assertEqual(record["inputs"]["body"], "@outputs('Game_result')")
        self.assertEqual(record["inputs"]["retryPolicy"]["type"], "none")
        response = self.actions["Respond_with_result"]
        self.assertEqual(response["runAfter"], {"Finalize_game": ["Succeeded"]})
        self.assertEqual(response["inputs"]["body"]["session"], "@body('Record_session')")
        self.assertEqual(response["inputs"]["body"]["message"], "@variables('lastMessage')")
        self.assertEqual(self.actions["End_conversation"]["runAfter"], {
            "Respond_with_result": ["Succeeded"],
        })
        self.assertEqual(self.actions["End_conversation"]["inputs"]["runStatus"], "Succeeded")
        self.assertEqual(self.actions["Respond_with_error"]["inputs"]["statusCode"], 502)
        self.assertEqual(self.actions["Respond_with_error"]["runAfter"], {
            "Finalize_game": ["Failed", "Skipped", "TimedOut"],
        })
        self.assertEqual(self.actions["Fail_run"]["inputs"]["runStatus"], "Failed")

    def test_failed_turn_stops_loop_and_cannot_be_recorded_as_a_game(self):
        catch = self.loop["actions"]["Mark_failed_turn"]
        self.assertEqual(catch["runAfter"], {
            "Check_win_or_turn_limit": ["Failed", "Skipped", "TimedOut"],
        })
        self.assertEqual(catch["inputs"], {"name": "gameFailed", "value": True})
        self.assertIn("variables('gameFailed')", self.loop["expression"])
        completion = self.game["Validate_game_completion"]
        self.assertEqual(completion["inputs"]["content"]["failed"], "@variables('gameFailed')")
        self.assertEqual(completion["inputs"]["schema"]["properties"]["failed"]["enum"], [False])
        self.assertEqual(completion["inputs"]["schema"]["properties"]["status"]["enum"], ["won", "lost"])

    def test_action_dependencies_resolve(self):
        def check(actions):
            for action in actions.values():
                for dependency in action.get("runAfter", {}):
                    self.assertIn(dependency, actions)
                if "actions" in action:
                    check(action["actions"])
                if "else" in action:
                    check(action["else"]["actions"])
        check(self.actions)
        for workflow in self.turn_workflows.values():
            check(workflow["definition"]["actions"])


if __name__ == "__main__":
    unittest.main()
