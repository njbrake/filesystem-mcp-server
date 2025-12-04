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
INIT_RESPONSE=$(curl -s -X POST "http://localhost:$PORT/mcp" \
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

if echo "$INIT_RESPONSE" | jq -e '.result' > /dev/null 2>&1; then
  echo "✓ Session initialized"
else
  echo "✗ Session initialization failed"
  echo "Response: $INIT_RESPONSE"
  docker logs "$CONTAINER_NAME"
  exit 1
fi
echo ""

echo "Test 2: Listing tools..."
TOOLS_RESPONSE=$(curl -s -X POST "http://localhost:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}')

TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | jq '.result.tools | length' 2>/dev/null || echo "0")
if [ "$TOOL_COUNT" -ge 8 ]; then
  echo "✓ Found $TOOL_COUNT tools"
else
  echo "✗ Expected at least 8 tools, got $TOOL_COUNT"
  echo "Response: $TOOLS_RESPONSE"
  exit 1
fi
echo ""

echo "=== All tests passed! ==="
