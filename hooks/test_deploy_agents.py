import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import deploy_agents


class HostedDeploymentTests(unittest.TestCase):
    def client(self):
        client = MagicMock()
        client.agents.create_version.return_value = SimpleNamespace(
            name="ollama-agent", version="2",
        )
        client.get_openai_client.return_value.__enter__.return_value.responses.create.return_value = (
            SimpleNamespace(status="completed", output_text="Paris is in France.", error=None)
        )
        return client

    @patch("deploy_agents.save_outputs")
    @patch("deploy_agents.time.sleep")
    def test_uses_responses_2_and_waits_for_provisioning_before_agent_scoped_inference(self, sleep, save):
        client = self.client()
        client.agents.get_version.side_effect = [
            SimpleNamespace(status="creating"), SimpleNamespace(status="active"),
        ]
        with patch("deploy_agents.AIProjectClient", return_value=client) as project_client, patch(
                "deploy_agents.CONTAINER_IMAGE", "registry.example/agent:versioned"), contextlib.redirect_stdout(io.StringIO()):
            deploy_agents.create_hosted_agent()
        self.assertTrue(project_client.call_args.kwargs["allow_preview"])
        definition = client.agents.create_version.call_args.kwargs["definition"].as_dict()
        self.assertEqual(definition["protocol_versions"], [{"protocol": "responses", "version": "2.0.0"}])
        self.assertEqual((definition["cpu"], definition["memory"]), ("4", "8Gi"))
        self.assertEqual(definition["container_configuration"]["image"], "registry.example/agent:versioned")
        self.assertEqual(definition["environment_variables"]["PYTHONNOUSERSITE"], "1")
        self.assertNotIn("image", definition)
        self.assertNotIn("APPLICATIONINSIGHTS_CONNECTION_STRING", definition["environment_variables"])
        sleep.assert_called_once_with(10)
        client.get_openai_client.assert_called_once_with(agent_name="ollama-agent", timeout=600)
        save.assert_called_once_with({
            "HOSTED_AGENT_VERSION": "2", "CONTAINER_IMAGE": "registry.example/agent:versioned",
        })

    @patch("deploy_agents.save_outputs")
    def test_failed_provisioning_cannot_be_reported_as_deployment_success(self, save):
        client = self.client()
        client.agents.get_version.return_value = SimpleNamespace(status="failed", error=None)
        with patch("deploy_agents.AIProjectClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "entered status failed"):
                deploy_agents.create_hosted_agent()
        client.get_openai_client.assert_not_called()
        save.assert_not_called()

    @patch("deploy_agents.save_outputs")
    def test_failed_provisioning_reports_the_service_error(self, save):
        client = self.client()
        client.agents.get_version.return_value = SimpleNamespace(
            status="failed",
            error=SimpleNamespace(code="ImageError", message="The image is too large."),
        )
        with patch("deploy_agents.AIProjectClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "ImageError: The image is too large"):
                deploy_agents.create_hosted_agent()
        client.get_openai_client.assert_not_called()
        save.assert_not_called()

    @patch("deploy_agents.save_outputs")
    @patch("deploy_agents.time.monotonic", side_effect=[0, 1800])
    def test_provisioning_has_a_deadline(self, monotonic, save):
        client = self.client()
        with patch("deploy_agents.AIProjectClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(TimeoutError):
                deploy_agents.create_hosted_agent()
        save.assert_not_called()

    @patch("deploy_agents.save_outputs")
    def test_incomplete_or_empty_inference_is_not_success(self, save):
        for status, text in [("failed", ""), ("in_progress", "partial"), ("completed", "")]:
            client = self.client()
            client.agents.get_version.return_value = SimpleNamespace(status="active")
            client.get_openai_client.return_value.__enter__.return_value.responses.create.return_value = (
                SimpleNamespace(status=status, output_text=text, error="verification-error")
            )
            with self.subTest(status=status, text=text), patch(
                    "deploy_agents.AIProjectClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "did not complete"):
                    deploy_agents.create_hosted_agent()
        save.assert_not_called()

    @patch("deploy_agents.save_outputs")
    def test_managed_agent_versions_are_saved_for_automation_binding(self, save):
        client = MagicMock()
        client.agents.create_version.side_effect = [
            SimpleNamespace(name="player", id="player:2", version="2"),
            SimpleNamespace(name="gameMaster", id="gameMaster:3", version="3"),
        ]
        with patch("deploy_agents.AIProjectClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            deploy_agents.create_managed_agents()
        save.assert_called_once_with({"PLAYER_AGENT_VERSION": "2", "GAME_MASTER_AGENT_VERSION": "3"})
        instructions = client.agents.create_version.call_args.kwargs["definition"].instructions
        self.assertIn("Automation turn mode takes precedence", instructions)
        self.assertIn("Otherwise, for an interactive game", instructions)


if __name__ == "__main__":
    unittest.main()
