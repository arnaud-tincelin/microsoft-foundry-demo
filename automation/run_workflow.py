"""Invoke the published Logic Apps Automation workflow. Uses only the standard library."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_result(result):
    if not isinstance(result, dict):
        raise ValueError("Workflow response must be a JSON object.")
    if result.get("status") not in ("won", "lost"):
        raise ValueError("Workflow did not return a won/lost result.")
    number = result.get("number_picked")
    if type(number) is not int or not 1 <= number <= 100:
        raise ValueError("Workflow must return number_picked as an integer from 1 to 100.")
    turns = result.get("turns")
    if type(turns) is not int or not 1 <= turns <= 10:
        raise ValueError("Workflow must return turns as an integer from 1 to 10.")
    if result["status"] == "lost" and turns != 10:
        raise ValueError("A lost game must use all 10 guesses.")
    message = result.get("message")
    if not isinstance(message, dict) or message.get("status") != result["status"]:
        raise ValueError("Workflow must return the final won/lost message.")
    if result["status"] == "won":
        if type(message.get("number")) is not int or message["number"] != number:
            raise ValueError("The winning message must contain the actual secret number.")
    elif message.get("number") != "-1":
        raise ValueError("The loss message must contain the original -1 sentinel.")
    if not isinstance(result.get("conversation_id"), str) or not result["conversation_id"]:
        raise ValueError("Workflow must return a non-empty conversation_id.")
    session = result.get("session")
    if not isinstance(session, dict) or not isinstance(session.get("session_id"), str) or not session["session_id"]:
        raise ValueError("Workflow did not confirm that the session was recorded.")
    return result


def run_workflow(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("LOGIC_APPS_WORKFLOW_URL must be an HTTPS callback URL.")
    request = Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=360) as response:
            if response.status != 200:
                raise ValueError(
                    f"Workflow returned HTTP {response.status}, not a completed game. "
                    "Check the Response action and Automation run history."
                )
            result = json.load(response)
    except HTTPError as error:
        # Do not print the exception URL: callback URLs can contain access signatures.
        raise RuntimeError(
            f"Workflow returned HTTP {error.code}. Review the Automation run history."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError(
            "Workflow connection failed or timed out. Check run history before retrying; "
            "the workflow might still be running."
        ) from None
    return validate_result(result)


def main():
    url = os.environ.get("LOGIC_APPS_WORKFLOW_URL", "")
    if not url:
        print("Set LOGIC_APPS_WORKFLOW_URL to the published workflow's HTTP callback URL.", file=sys.stderr)
        return 1
    try:
        result = run_workflow(url)
    except (ValueError, RuntimeError) as error:
        print(f"Automation error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
