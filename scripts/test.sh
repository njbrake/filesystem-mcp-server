#!/bin/bash
set -e

IMAGE="${1:-filesystem-mcp-server:test}"
CONTAINER_NAME="mcp-test"
PORT=8123
TEST_DIR="/tmp/mcp-test-data"

echo "=== Filesystem MCP Server Docker Tests ==="
echo "Image: $IMAGE"
echo ""

cleanup() {
  echo "Cleaning up..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
  rm -rf "$TEST_DIR"
}

trap cleanup EXIT

echo "Setting up test environment..."
mkdir -p "$TEST_DIR"
echo "Test file content" > "$TEST_DIR/existing.txt"

echo "Starting container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PORT:$PORT" \
  -v "$TEST_DIR:/data" \
  "$IMAGE"

echo "Waiting for server to start..."
for i in {1..30}; do
  if curl -sf "http://localhost:$PORT/mcp" > /dev/null 2>&1 || [ $? -eq 22 ]; then
    echo "✓ Server is ready!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "✗ Server failed to start"
    docker logs "$CONTAINER_NAME"
    exit 1
  fi
  sleep 1
done
echo ""

echo "Test 1: Initialize session..."
INIT_RESPONSE=$(curl -s -i -X POST "http://localhost:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0",
    "method":"initialize",
    "params":{
      "protocolVersion":"2024-11-05",
      "capabilities":{},
      "clientInfo":{"name":"test-client","version":"1.0.0"}
    },
    "id":1
  }')

echo "  Response headers:"
echo "$INIT_RESPONSE" | grep -i "HTTP/\|content-type\|mcp-session-id" | sed 's/^/    /'

# Extract session ID from headers
SESSION_ID=$(echo "$INIT_RESPONSE" | grep -i "^mcp-session-id:" | sed 's/^mcp-session-id: //i' | tr -d '\r\n')
if [ -n "$SESSION_ID" ]; then
  echo "  ✓ Session ID: $SESSION_ID"
else
  echo "  ⚠ No Mcp-Session-Id header found"
fi

# Parse SSE response (extract JSON from "data: " line)
INIT_JSON=$(echo "$INIT_RESPONSE" | grep "^data: " | sed 's/^data: //')
if echo "$INIT_JSON" | jq -e '.result' > /dev/null 2>&1; then
  SERVER_NAME=$(echo "$INIT_JSON" | jq -r '.result.serverInfo.name')
  echo "  ✓ Session initialized (server: $SERVER_NAME)"
else
  echo "✗ Session initialization failed"
  echo "Full Response:"
  echo "$INIT_RESPONSE"
  docker logs "$CONTAINER_NAME"
  exit 1
fi
echo ""

echo "Test 2: Listing tools (with session ID)..."
if [ -n "$SESSION_ID" ]; then
  TOOLS_RESPONSE=$(curl -s -i -X POST "http://localhost:$PORT/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":2}')
  echo "  Using session ID: $SESSION_ID"
else
  TOOLS_RESPONSE=$(curl -s -i -X POST "http://localhost:$PORT/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","method":"tools/list","id":2}')
  echo "  No session ID available"
fi

echo "  Response headers:"
echo "$TOOLS_RESPONSE" | grep -i "HTTP/\|content-type" | sed 's/^/    /'

# Parse SSE response
TOOLS_JSON=$(echo "$TOOLS_RESPONSE" | grep "^data: " | sed 's/^data: //')
TOOL_COUNT=$(echo "$TOOLS_JSON" | jq '.result.tools | length' 2>/dev/null || echo "0")
if [ "$TOOL_COUNT" -ge 8 ]; then
  echo "  ✓ Found $TOOL_COUNT tools"
  # Show first few tool names
  TOOL_NAMES=$(echo "$TOOLS_JSON" | jq -r '.result.tools[0:3] | .[].name' | tr '\n' ', ' | sed 's/,$//')
  echo "  Tools: $TOOL_NAMES..."
else
  echo "✗ Expected at least 8 tools, got $TOOL_COUNT"
  echo "Full Response:"
  echo "$TOOLS_RESPONSE"
  exit 1
fi
echo ""

echo "=== All tests passed! ==="
