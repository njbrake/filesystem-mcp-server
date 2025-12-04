"""Tests for the filesystem MCP server."""

import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.middleware import Middleware

from filesystem.server import ALLOWED_ROOT, TrustedHostMiddleware, mcp


@pytest.fixture(scope="session")
def temp_dir_session():
    """Create a temporary directory for the entire test session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_app_session(temp_dir_session):
    """Create test ASGI app with temporary allowed root and proper lifespan (session-scoped)."""
    import filesystem.server

    filesystem.server.ALLOWED_ROOT = temp_dir_session

    # Create middleware list
    middleware = [Middleware(TrustedHostMiddleware)]

    # Create app with middleware using http_app() with streamable-http transport
    mcp_app = mcp.http_app(
        transport="streamable-http",
        middleware=middleware,
        json_response=False,
        stateless_http=False,
    )

    # Manage lifespan properly for testing
    async with mcp_app.lifespan(None):
        yield mcp_app


@pytest.fixture
def temp_dir(temp_dir_session):
    """Per-test temp dir reference (just returns session dir)."""
    return temp_dir_session


@pytest.fixture
async def test_app(test_app_session, temp_dir):
    """Per-test app fixture that resets ALLOWED_ROOT."""
    import filesystem.server
    filesystem.server.ALLOWED_ROOT = temp_dir
    return test_app_session


@pytest.fixture
async def client(test_app):
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def session(client):
    """Initialize an MCP session and return session ID."""
    response = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
            "id": 1,
        },
        headers={"Accept": "application/json, text/event-stream"},
    )

    assert response.status_code == 200
    session_id = response.headers.get("mcp-session-id")
    assert session_id is not None

    lines = response.text.strip().split("\n")
    data_line = next(line for line in lines if line.startswith("data: "))
    data = json.loads(data_line.replace("data: ", ""))

    assert "result" in data
    assert data["result"]["serverInfo"]["name"] == "filesystem"

    return session_id


class TestMCPProtocol:
    """Test MCP protocol implementation."""

    @pytest.mark.asyncio
    async def test_initialize(self, client):
        """Test session initialization."""
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
                "id": 1,
            },
            headers={"Accept": "application/json, text/event-stream"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert response.headers.get("mcp-session-id") is not None

        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"
        assert data["result"]["serverInfo"]["name"] == "filesystem"

    @pytest.mark.asyncio
    async def test_list_tools(self, client, session):
        """Test listing available tools."""
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200

        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        assert "result" in data
        tools = data["result"]["tools"]
        assert len(tools) == 8

        tool_names = {tool["name"] for tool in tools}
        expected_tools = {
            "read_file",
            "list_directory",
            "write_file",
            "create_directory",
            "delete_file",
            "delete_directory",
            "move_path",
            "get_file_info",
        }
        assert tool_names == expected_tools


class TestFilesystemOperations:
    """Test filesystem tool operations."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, client, session, temp_dir):
        """Test writing and reading a file."""
        write_response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "write_file",
                    "arguments": {"path": "test.txt", "content": "Hello, World!"},
                },
                "id": 3,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert write_response.status_code == 200
        lines = write_response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))
        assert "result" in data
        assert "Successfully wrote" in data["result"]["content"][0]["text"]

        assert (temp_dir / "test.txt").exists()
        assert (temp_dir / "test.txt").read_text() == "Hello, World!"

        read_response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "read_file", "arguments": {"path": "test.txt"}},
                "id": 4,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert read_response.status_code == 200
        lines = read_response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))
        assert data["result"]["content"][0]["text"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_list_directory(self, client, session, temp_dir):
        """Test listing directory contents."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "list_directory", "arguments": {"path": "."}},
                "id": 5,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        content = data["result"]["content"][0]["text"]
        assert "file1.txt" in content
        assert "file2.txt" in content
        assert "subdir" in content

    @pytest.mark.asyncio
    async def test_create_directory(self, client, session, temp_dir):
        """Test creating a directory."""
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "create_directory",
                    "arguments": {"path": "newdir/subdir"},
                },
                "id": 6,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        assert (temp_dir / "newdir" / "subdir").exists()
        assert (temp_dir / "newdir" / "subdir").is_dir()

    @pytest.mark.asyncio
    async def test_delete_file(self, client, session, temp_dir):
        """Test deleting a file."""
        test_file = temp_dir / "to_delete.txt"
        test_file.write_text("delete me")

        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "delete_file", "arguments": {"path": "to_delete.txt"}},
                "id": 7,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_directory(self, client, session, temp_dir):
        """Test deleting a directory."""
        test_dir = temp_dir / "to_delete"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "delete_directory",
                    "arguments": {"path": "to_delete", "recursive": True},
                },
                "id": 8,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        assert not test_dir.exists()

    @pytest.mark.asyncio
    async def test_move_path(self, client, session, temp_dir):
        """Test moving a file."""
        source = temp_dir / "source.txt"
        source.write_text("move me")

        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "move_path",
                    "arguments": {"source": "source.txt", "destination": "dest.txt"},
                },
                "id": 9,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        assert not source.exists()
        assert (temp_dir / "dest.txt").exists()
        assert (temp_dir / "dest.txt").read_text() == "move me"

    @pytest.mark.asyncio
    async def test_get_file_info(self, client, session, temp_dir):
        """Test getting file metadata."""
        test_file = temp_dir / "info.txt"
        test_file.write_text("test content")

        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "get_file_info", "arguments": {"path": "info.txt"}},
                "id": 10,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        content = data["result"]["content"][0]["text"]
        assert "Path: info.txt" in content
        assert "Type: File" in content
        assert "Size: 12 bytes" in content


class TestSecurity:
    """Test security features."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, client, session):
        """Test that path traversal attacks are blocked."""
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "read_file",
                    "arguments": {"path": "../../../etc/passwd"},
                },
                "id": 11,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        assert "result" in data
        assert data["result"]["isError"] is True
        assert "outside allowed root" in data["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_absolute_path_blocked(self, client, session):
        """Test that absolute paths outside allowed root are blocked."""
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "read_file", "arguments": {"path": "/etc/passwd"}},
                "id": 12,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session,
            },
        )

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        data_line = next(line for line in lines if line.startswith("data: "))
        data = json.loads(data_line.replace("data: ", ""))

        assert "result" in data
        assert data["result"]["isError"] is True
        assert "outside allowed root" in data["result"]["content"][0]["text"]


class TestTrustedHostMiddleware:
    """Test trusted host middleware."""

    @pytest.mark.asyncio
    async def test_accepts_any_hostname(self, client):
        """Test that middleware accepts any Host header."""
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
                "id": 1,
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Host": "recipes-mcp:8123",
            },
        )

        assert response.status_code == 200
        assert "mcp-session-id" in response.headers
