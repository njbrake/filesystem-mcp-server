# filesystem-mcp-server

Filesystem MCP server with Streamable HTTP transport support. Provides comprehensive filesystem operations through the Model Context Protocol.

Created as an alternative to the [official MCP filesystem server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) with modern Streamable HTTP transport instead of deprecated SSE.

## Features

- **Streamable HTTP Transport** - Modern MCP protocol
- **8 Filesystem Operations** - Read, write, list, create, delete, move, and inspect files/directories
- **Security First** - Configurable root directory with path traversal protection
- **Docker Ready** - Multi-arch images (amd64/arm64) published to GHCR

## Quick Start

### Docker (Recommended)

```bash
docker pull ghcr.io/njbrake/filesystem-mcp-server:main

docker run -d \
  --name filesystem-mcp \
  -p 8123:8123 \
  -v /path/to/your/files:/data \
  ghcr.io/njbrake/filesystem-mcp-server:main
```

**Available tags:** `main` (latest), `v*` (releases), `main-<sha>` (commits)

### Python with uv

```bash
cd filesystem-mcp-server
uv sync
uv run filesystem-mcp --allowed-root /path/to/files --port 8123
```

Server endpoint: `http://localhost:8123/mcp`

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 8123 | Port to listen on |
| `--allowed-root` | `.` | Root directory for filesystem operations |

## Available Tools

The server exposes 8 MCP tools for filesystem operations:

| Tool | Description | Parameters |
|------|-------------|------------|
| `read_file` | Read file contents as text | `path` |
| `list_directory` | List directory contents with metadata | `path` (optional, default: ".") |
| `write_file` | Create or overwrite a file | `path`, `content` |
| `create_directory` | Create directory (with parents) | `path` |
| `delete_file` | Delete a file | `path` |
| `delete_directory` | Delete directory | `path`, `recursive` (optional) |
| `move_path` | Move or rename file/directory | `source`, `destination` |
| `get_file_info` | Get file/directory metadata | `path` |

All paths are relative to the configured `--allowed-root`.

## Security

The `--allowed-root` parameter restricts all filesystem operations to the specified directory tree. Path validation prevents directory traversal attacks:

1. Paths are resolved relative to allowed root
2. Symlinks and `..` components are canonicalized
3. Final path must be within allowed root
4. Attempts to escape are rejected (e.g., `../../../etc/passwd`)

**Important:** Never run with system-critical directories as the allowed root.

## Docker Details

### Custom Configuration

```bash
# Different port
docker run -p 8000:8000 \
  -v /my/files:/data \
  ghcr.io/njbrake/filesystem-mcp-server:main \
  --allowed-root /data --port 8000

# Build locally
docker build -t filesystem-mcp-server .
```

### Container Details
- Default port: 8123
- Default allowed root: `/data`
- Volume mount point: `/data`
- Multi-architecture: linux/amd64, linux/arm64

## Testing

```bash
# List available tools
curl -X POST http://localhost:8123/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Read a file
curl -X POST http://localhost:8123/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"read_file",
      "arguments":{"path":"README.md"}
    },
    "id":2
  }'
```

## About MCP

This server implements the [Model Context Protocol](https://modelcontextprotocol.io/), an open protocol for seamless integration between LLM applications and external tools.

Uses **Streamable HTTP transport** (MCP spec 2025-03-26), the modern replacement for deprecated HTTP+SSE.
