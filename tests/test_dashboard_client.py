from unittest.mock import Mock, patch

from dashboard.api_client import TrialGuardAPI


def test_request_allows_timeout_override_without_duplicate_keyword():
    api = TrialGuardAPI("http://example.test", timeout=20.0)
    response = Mock()
    response.status_code = 200
    response.content = b'{}'
    response.json.return_value = {}

    with patch("dashboard.api_client.requests.request", return_value=response) as request:
        api._request("POST", "/agent", timeout=120.0, json={"x": 1})

    request.assert_called_once_with(
        "POST",
        "http://example.test/agent",
        timeout=120.0,
        json={"x": 1},
    )
