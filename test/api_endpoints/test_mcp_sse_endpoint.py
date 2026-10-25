import json
from unittest.mock import patch
from urllib.parse import urljoin, urlparse

import pytest

from api_server import mcp_endpoint
from api_server.api_server_start import app
from helper import get_setting_value


@pytest.fixture(scope="session")
def api_token():
    """Return the API token from the loaded config."""
    return get_setting_value("API_TOKEN")


@pytest.fixture(autouse=True)
def clear_mcp_sessions():
    """Ensure MCP session state is clean before and after every test."""
    with mcp_endpoint._sessions_lock:
        mcp_endpoint._mcp_sessions.clear()
    yield
    with mcp_endpoint._sessions_lock:
        mcp_endpoint._mcp_sessions.clear()


@pytest.fixture
def client():
    """Yield a Flask test client for the API server."""
    with app.test_client() as client:
        yield client


def auth_headers(api_token, **extra):
    headers = {"Authorization": f"Bearer {api_token}"}
    headers.update(extra)
    return headers


def read_endpoint_event(client, api_token):
    """Open the MCP SSE stream and return the data of its first (endpoint) event."""
    response = client.get("/mcp/sse", headers={"Authorization": f"Bearer {api_token}"}, buffered=False)
    assert response.status_code == 200
    assert response.headers.get("Deprecation") == "true"
    assert '</mcp>; rel="successor-version"' in response.headers.get("Link", "")
    try:
        first_event = next(response.response)
    finally:
        response.close()
    if isinstance(first_event, bytes):
        first_event = first_event.decode()
    lines = first_event.strip().splitlines()
    assert lines[0] == "event: endpoint"
    return lines[1].removeprefix("data: ")


@pytest.mark.parametrize("sse_url, expected_path", [
    ("http://host:20212/mcp/sse", "/mcp/messages"),
    ("http://host:20211/server/mcp/sse", "/server/mcp/messages"),
])
def test_sse_endpoint_resolves_to_messages_route(client, api_token, sse_url, expected_path):
    """The advertised endpoint must resolve to the messages route both directly and behind the /server proxy prefix."""
    endpoint = read_endpoint_event(client, api_token)
    resolved = urlparse(urljoin(sse_url, endpoint))
    assert resolved.path == expected_path
    assert resolved.query.startswith("session_id=")


# =============================================================================
# STREAMABLE HTTP (/mcp) TESTS
# =============================================================================

@pytest.mark.parametrize("client_version, expected_version", [
    ("2025-03-26", "2025-03-26"),
    ("2025-06-18", "2025-06-18"),
    ("2024-11-05", "2024-11-05"),
    ("2099-01-01", "2025-03-26"),
])
def test_mcp_streamable_http_initialize_version_negotiation(client, api_token, client_version, expected_version):
    """POST /mcp initialize negotiates protocolVersion and issues Mcp-Session-Id header."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": client_version,
            "capabilities": {},
            "clientInfo": {"name": "pytest-client", "version": "1.0.0"}
        }
    }
    resp = client.post("/mcp", json=payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    session_id = resp.headers.get("Mcp-Session-Id")
    assert session_id is not None
    assert mcp_endpoint.is_valid_session_id(session_id)
    assert resp.headers.get("MCP-Protocol-Version") == expected_version

    body = resp.get_json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["protocolVersion"] == expected_version
    assert body["result"]["serverInfo"]["name"] == "NetAlertX"


def test_mcp_streamable_http_initialize_rejects_preset_session_id(client, api_token):
    """POST /mcp initialize must reject a client-supplied Mcp-Session-Id (anti-session-fixation)."""
    preset_id = "a" * 32
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26"}
    }
    resp = client.post(
        "/mcp",
        json=payload,
        headers=auth_headers(api_token, **{"Mcp-Session-Id": preset_id})
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"]["code"] == -32600


def test_mcp_streamable_http_rejects_unsupported_protocol_header(client, api_token):
    """Requests with an unsupported MCP-Protocol-Version header must return 400."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    resp = client.post(
        "/mcp",
        json=payload,
        headers=auth_headers(api_token, **{"MCP-Protocol-Version": "1999-01-01"})
    )
    assert resp.status_code == 400


def test_mcp_streamable_http_stateful_lifecycle(client, api_token):
    """Full stateful lifecycle: initialize -> notifications/initialized (202) -> ping -> DELETE /mcp (200) -> 404."""
    # 1. Initialize
    init_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        headers=auth_headers(api_token)
    )
    assert init_resp.status_code == 200
    session_id = init_resp.headers["Mcp-Session-Id"]

    # 2. Send notifications/initialized -> 202 Accepted with empty body
    notif_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=auth_headers(api_token, **{"Mcp-Session-Id": session_id})
    )
    assert notif_resp.status_code == 202
    assert notif_resp.get_data(as_text=True) == ""

    # 3. Stateful ping
    ping_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "ping"},
        headers=auth_headers(api_token, **{"Mcp-Session-Id": session_id})
    )
    assert ping_resp.status_code == 200
    assert ping_resp.get_json()["result"] == {}
    assert ping_resp.headers.get("Mcp-Session-Id") == session_id

    # 4. Terminate session via DELETE /mcp
    del_resp = client.delete(
        "/mcp",
        headers=auth_headers(api_token, **{"Mcp-Session-Id": session_id})
    )
    assert del_resp.status_code == 200
    assert del_resp.get_json()["status"] == "terminated"

    # 5. Subsequent DELETE or POST with terminated session_id returns 404
    del_again = client.delete(
        "/mcp",
        headers=auth_headers(api_token, **{"Mcp-Session-Id": session_id})
    )
    assert del_again.status_code == 404

    post_after_del = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 3, "method": "ping"},
        headers=auth_headers(api_token, **{"Mcp-Session-Id": session_id})
    )
    assert post_after_del.status_code == 404


def test_mcp_streamable_http_session_id_validation(client, api_token):
    """Malformed Mcp-Session-Id returns 400; unknown valid-format Mcp-Session-Id returns 404."""
    # Malformed session ID
    bad_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers=auth_headers(api_token, **{"Mcp-Session-Id": "not-a-valid-hex-id!"})
    )
    assert bad_resp.status_code == 400

    # Unknown 32-char hex session ID
    unknown_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers=auth_headers(api_token, **{"Mcp-Session-Id": "0" * 32})
    )
    assert unknown_resp.status_code == 404

    # DELETE without Mcp-Session-Id header -> 400
    del_missing = client.delete("/mcp", headers=auth_headers(api_token))
    assert del_missing.status_code == 400


@pytest.mark.parametrize("method", ["tools/list", "resources/list", "prompts/list", "ping"])
def test_mcp_streamable_http_stateless_methods(client, api_token, method):
    """Stateless POST /mcp calls without Mcp-Session-Id succeed directly."""
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 10, "method": method},
        headers=auth_headers(api_token)
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 10
    assert "result" in body


@patch("api_server.mcp_endpoint._execute_tool")
def test_mcp_streamable_http_stateless_tools_call(mock_exec, client, api_token):
    """Stateless POST /mcp tools/call executes the requested tool."""
    mock_exec.return_value = {"content": [{"type": "text", "text": "{\"ok\": true}"}], "isError": False}
    with patch("api_server.mcp_endpoint.find_route_for_tool", return_value={"path": "/devices/totals", "method": "GET", "operation_id": "get_device_totals"}):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "get_device_totals", "arguments": {}}
            },
            headers=auth_headers(api_token)
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["result"]["isError"] is False


def test_mcp_streamable_http_jsonrpc_batching(client, api_token):
    """POST /mcp supports JSON-RPC batch arrays and enforces batch constraints."""
    # 1. Valid mixed batch (requests + notification)
    batch_payload = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "prompts/list"},
    ]
    resp = client.post("/mcp", json=batch_payload, headers=auth_headers(api_token))
    assert resp.status_code == 200
    results = resp.get_json()
    assert isinstance(results, list)
    assert len(results) == 2
    assert {r["id"] for r in results} == {1, 2}

    # 2. Notifications-only batch -> 202
    notif_batch = [
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "method": "notifications/cancelled"},
    ]
    notif_resp = client.post("/mcp", json=notif_batch, headers=auth_headers(api_token))
    assert notif_resp.status_code == 202
    assert notif_resp.get_data(as_text=True) == ""

    # 3. Empty batch [] -> 400
    empty_resp = client.post("/mcp", json=[], headers=auth_headers(api_token))
    assert empty_resp.status_code == 400

    # 4. Oversized batch (> MAX_BATCH_SIZE) -> 400
    oversized = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(mcp_endpoint.MAX_BATCH_SIZE + 1)]
    over_resp = client.post("/mcp", json=oversized, headers=auth_headers(api_token))
    assert over_resp.status_code == 400

    # 5. Batch containing initialize mixed with another request -> 400
    mixed_init = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ]
    mixed_resp = client.post("/mcp", json=mixed_init, headers=auth_headers(api_token))
    assert mixed_resp.status_code == 400


def test_mcp_streamable_http_payload_size_limit(client, api_token):
    """POST /mcp payloads exceeding MAX_MCP_BODY_BYTES return 413 Payload Too Large."""
    oversized_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping",
        "params": {"padding": "x" * (mcp_endpoint.MAX_MCP_BODY_BYTES + 1024)}
    })
    resp = client.post(
        "/mcp",
        data=oversized_body,
        content_type="application/json",
        headers=auth_headers(api_token)
    )
    assert resp.status_code == 413


def test_mcp_streamable_http_get_standalone_sse_stream(client, api_token):
    """GET /mcp streams queued JSON-RPC messages without emitting the legacy endpoint event."""
    # Create session via initialize
    init_resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        headers=auth_headers(api_token)
    )
    session_id = init_resp.headers["Mcp-Session-Id"]

    # Enqueue a server message onto the session queue
    session = mcp_endpoint.get_session(session_id)
    queued_msg = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"data": "hello"}}
    session["queue"].put(queued_msg)

    response = client.get(
        "/mcp",
        headers=auth_headers(api_token, Accept="text/event-stream", **{"Mcp-Session-Id": session_id}),
        buffered=False
    )
    assert response.status_code == 200
    try:
        first_chunk = next(response.response)
    finally:
        response.close()

    if isinstance(first_chunk, bytes):
        first_chunk = first_chunk.decode()
    assert "event: endpoint" not in first_chunk
    lines = first_chunk.strip().splitlines()
    assert lines[0] == "event: message"
    assert json.loads(lines[1].removeprefix("data: ")) == queued_msg


def test_mcp_streamable_http_get_rejects_non_sse_accept(client, api_token):
    """GET /mcp with Accept: application/json (excluding text/event-stream) returns 406."""
    resp = client.get(
        "/mcp",
        headers=auth_headers(api_token, Accept="application/json")
    )
    assert resp.status_code == 406


def test_mcp_max_active_sessions_cap(client, api_token):
    """Creating more than MAX_ACTIVE_SESSIONS concurrent sessions returns 503."""
    for i in range(mcp_endpoint.MAX_ACTIVE_SESSIONS):
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": i + 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
            headers=auth_headers(api_token)
        )
        assert r.status_code == 200

    overflow = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 999, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        headers=auth_headers(api_token)
    )
    assert overflow.status_code == 503


def test_legacy_sse_and_messages_flow_with_deprecation_headers(client, api_token):
    """Legacy /mcp/sse + /mcp/messages flow remains functional and includes Deprecation headers."""
    endpoint = read_endpoint_event(client, api_token)
    resolved = urlparse(urljoin("http://host:20212/mcp/sse", endpoint))
    msg_url = f"{resolved.path}?{resolved.query}"

    post_resp = client.post(
        msg_url,
        json={"jsonrpc": "2.0", "id": 42, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        headers=auth_headers(api_token)
    )
    assert post_resp.status_code == 202
    assert post_resp.headers.get("Deprecation") == "true"
    assert '</mcp>; rel="successor-version"' in post_resp.headers.get("Link", "")

    # Also verify legacy stateless POST /mcp/sse and status fallback
    sse_post = client.post(
        "/mcp/sse",
        json={"jsonrpc": "2.0", "id": 43, "method": "ping"},
        headers=auth_headers(api_token)
    )
    assert sse_post.status_code == 200
    assert sse_post.headers.get("Deprecation") == "true"
    assert sse_post.get_json()["result"] == {}

    sse_notif = client.post(
        "/mcp/sse",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=auth_headers(api_token)
    )
    assert sse_notif.status_code == 202

    sse_status = client.post(
        "/mcp/sse",
        json={"ping": "status"},
        headers=auth_headers(api_token)
    )
    assert sse_status.status_code == 200
    assert sse_status.get_json()["status"] == "ok"


def test_mcp_prompts_and_resources_handlers(client, api_token, tmp_path):
    """Test prompts/get, resources/list, resources/read, and unknown method handling via POST /mcp."""
    # 1. prompts/get for all 3 built-in prompts + unknown + missing name
    for prompt_name, args in [
        ("analyze_network_health", {}),
        ("investigate_device", {"device_identifier": "aa:bb:cc:dd:ee:ff"}),
        ("troubleshoot_connectivity", {"target_ip": "192.168.1.1"}),
        ("unknown_prompt", {}),
    ]:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 50, "method": "prompts/get", "params": {"name": prompt_name, "arguments": args}},
            headers=auth_headers(api_token)
        )
        assert r.status_code == 200
        assert "messages" in r.get_json()["result"]

    missing_prompt = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 51, "method": "prompts/get", "params": {}},
        headers=auth_headers(api_token)
    )
    assert missing_prompt.get_json()["error"]["code"] == -32602

    # 2. resources/list and resources/read with temporary log dir
    log_dir = tmp_path / "logs"
    plugin_dir = log_dir / "plugins"
    plugin_dir.mkdir(parents=True)
    (log_dir / "app.log").write_text("line1\nline2\n", encoding="utf-8")
    (plugin_dir / "arpscan.log").write_text("plugin log line\n", encoding="utf-8")

    with patch.dict("os.environ", {"NETALERTX_LOG": str(log_dir)}):
        res_list = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 52, "method": "resources/list"},
            headers=auth_headers(api_token)
        )
        uris = [item["uri"] for item in res_list.get_json()["result"]["resources"]]
        assert "netalertx://api/openapi.json" in uris
        assert "netalertx://logs/app.log" in uris
        assert "netalertx://logs/plugins/arpscan.log" in uris

        # Read openapi.json resource
        read_spec = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 53, "method": "resources/read", "params": {"uri": "netalertx://api/openapi.json"}},
            headers=auth_headers(api_token)
        )
        assert read_spec.status_code == 200
        assert "openapi" in read_spec.get_json()["result"]["contents"][0]["text"]

        # Read app.log resource
        read_log = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 54, "method": "resources/read", "params": {"uri": "netalertx://logs/app.log"}},
            headers=auth_headers(api_token)
        )
        assert "line1" in read_log.get_json()["result"]["contents"][0]["text"]

        # Path traversal attempt outside log dir
        traversal = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 55, "method": "resources/read", "params": {"uri": "netalertx://logs/../../etc/passwd"}},
            headers=auth_headers(api_token)
        )
        assert "Access denied" in traversal.get_json()["result"]["contents"][0]["text"]

        # Non-existent log file
        not_found = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 56, "method": "resources/read", "params": {"uri": "netalertx://logs/missing.log"}},
            headers=auth_headers(api_token)
        )
        assert not_found.get_json()["result"]["contents"][0]["text"] == "File not found"

        # Unknown resource scheme
        unknown_uri = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 57, "method": "resources/read", "params": {"uri": "netalertx://unknown/item"}},
            headers=auth_headers(api_token)
        )
        assert unknown_uri.get_json()["result"]["contents"][0]["text"] == "Unknown resource type"

    # Missing resource URI
    missing_uri = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 58, "method": "resources/read", "params": {}},
        headers=auth_headers(api_token)
    )
    assert missing_uri.get_json()["error"]["code"] == -32602

    # Unknown method with id -> -32601
    unknown_method = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 59, "method": "nonexistent/method"},
        headers=auth_headers(api_token)
    )
    assert unknown_method.get_json()["error"]["code"] == -32601


@patch("api_server.mcp_endpoint.requests")
def test_mcp_execute_tool_http_methods_and_errors(mock_requests, client, api_token):
    """Test _execute_tool loopback execution across HTTP methods, validation, timeouts, and errors."""
    mock_resp = mock_requests.post.return_value
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}

    route_post = {
        "path": "/device/{mac}",
        "method": "POST",
        "operation_id": "update_device",
        "request_model": None,
    }
    with patch("api_server.mcp_endpoint.find_route_for_tool", return_value=route_post):
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 60,
                "method": "tools/call",
                "params": {"name": "update_device", "arguments": {"mac": "00:11:22:33:44:55", "devName": "Node"}}
            },
            headers=auth_headers(api_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["result"]["isError"] is False

    # Missing tool name & unknown tool
    no_name = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 61, "method": "tools/call", "params": {}},
        headers=auth_headers(api_token)
    )
    assert no_name.get_json()["error"]["code"] == -32602

    unknown_tool = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 62, "method": "tools/call", "params": {"name": "does_not_exist_tool"}},
        headers=auth_headers(api_token)
    )
    assert unknown_tool.get_json()["error"]["code"] == -32601

    # Single-element batch initialize & invalid JSON / OPTIONS
    batch_init = client.post(
        "/mcp",
        json=[{"jsonrpc": "2.0", "id": 63, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}],
        headers=auth_headers(api_token)
    )
    assert batch_init.status_code == 200
    assert batch_init.headers.get("Mcp-Session-Id") is not None

    bad_json = client.post(
        "/mcp",
        data="{bad json",
        content_type="application/json",
        headers=auth_headers(api_token)
    )
    assert bad_json.status_code == 400
    assert bad_json.get_json()["error"]["code"] == -32700

    opt_resp = client.options("/mcp")
    assert opt_resp.status_code == 200
    assert client.options("/mcp/sse").status_code == 200
    assert client.options("/mcp/messages").status_code == 200

    # Legacy /mcp/messages error branches
    assert client.post("/mcp/messages", headers=auth_headers(api_token)).status_code == 400
    assert client.post("/mcp/messages?session_id=bad", headers=auth_headers(api_token)).status_code == 400
    assert client.post(f"/mcp/messages?session_id={'0'*32}", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers=auth_headers(api_token)).status_code == 404

    sid = mcp_endpoint.create_session()
    assert client.post(f"/mcp/messages?session_id={sid}", data="not-json", content_type="application/json", headers=auth_headers(api_token)).status_code == 400

    # Ephemeral GET /mcp (without Mcp-Session-Id) and GET /mcp with unknown session_id
    assert client.get("/mcp", headers=auth_headers(api_token, Accept="text/event-stream", **{"Mcp-Session-Id": "0" * 32})).status_code == 404
    eph_resp = client.get("/mcp", headers=auth_headers(api_token, Accept="text/event-stream"), buffered=False)
    assert eph_resp.status_code == 200
    eph_sid = eph_resp.headers.get("Mcp-Session-Id")
    assert mcp_endpoint.is_valid_session_id(eph_sid)
    eph_resp.close()

    # Non-dict JSON body on POST /mcp (e.g. string/integer) and invalid batch element
    assert client.post("/mcp", data='"just a string"', content_type="application/json", headers=auth_headers(api_token)).status_code == 400
    assert client.post("/mcp", json=[{"not_jsonrpc": True}], headers=auth_headers(api_token)).status_code == 400
    assert client.post("/mcp", json={"jsonrpc": "1.0", "id": 1, "method": "ping"}, headers=auth_headers(api_token)).status_code == 400

    # openapi_spec() route handler with X-Forwarded-Prefix
    with app.test_request_context("/openapi.json", headers={"X-Forwarded-Prefix": "/app"}):
        spec_resp = mcp_endpoint.openapi_spec()
        assert spec_resp.status_code == 200
        assert spec_resp.get_json()["servers"][0]["url"] == "/app"

    # Expired session eviction in _evict_expired_sessions_locked()
    exp_sid = mcp_endpoint.create_session()
    with mcp_endpoint._sessions_lock:
        mcp_endpoint._mcp_sessions[exp_sid]["last_activity"] = 0
    assert mcp_endpoint.get_session(exp_sid) is None



