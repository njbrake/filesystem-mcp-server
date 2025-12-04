# filesystem-mcp-server

Modern Streamable HTTP supported filesystem MCP server that provides comprehensive filesystem operations through the Model Context Protocol.

I saw https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem but it didn't have the Streamable HTTP support that I wanted for my project.

## Features

- **Streamable HTTP Transport** - Uses the latest MCP Streamable HTTP protocol (not deprecated SSE)
- **Comprehensive Operations** - Read, write, list, create, delete, move, and get info on files and directories
- **Security First** - Configurable root directory prevents unauthorized filesystem access
- **Path Validation** - Built-in protection against directory traversal attacks
- **Type Safe** - Full Python type hints for better IDE support
- **Modern Python** - Built with Python 3.12+ and uv package manager

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install with uv

```bash
cd filesystem-mcp-server
uv sync
```

This will install all dependencies and make the `filesystem-mcp` command available.

### Using Docker

Pre-built Docker images are available from GitHub Container Registry (GHCR) for every commit and release.

#### Pull and run from GHCR

```bash
# Pull the latest image
docker pull ghcr.io/<username>/filesystem-mcp-server:latest

# Run with a volume mount
docker run -d \
  --name filesystem-mcp \
  -p 8123:8123 \
  -v /path/to/your/files:/data \
  ghcr.io/<username>/filesystem-mcp-server:latest

# Run with custom settings
docker run -d \
  --name filesystem-mcp \
  -p 8000:8000 \
  -v /path/to/your/files:/data \
  ghcr.io/<username>/filesystem-mcp-server:latest \
  --allowed-root /data --port 8000
```

#### Build locally

```bash
# Build the Docker image
docker build -t filesystem-mcp-server .

# Run the container
docker run -d \
  --name filesystem-mcp \
  -p 8123:8123 \
  -v /path/to/your/files:/data \
  filesystem-mcp-server
```

#### Docker Image Tags

- `latest` - Built from the latest commit on main branch
- `v*` - Specific version tags (e.g., `v0.1.0`)
- `main-<sha>` - Specific commit from main branch
- Multi-architecture support: `linux/amd64`, `linux/arm64`

#### Docker Notes

- The container exposes port **8123** by default
- Mount a volume to **/data** to provide access to your files
- The default allowed root is `/data` inside the container
- You can override the entrypoint arguments to customize port and allowed root

## Usage

### Start the Server

```bash
# Run with default settings (current directory, port 8123)
uv run filesystem-mcp

# Specify a different root directory
uv run filesystem-mcp --allowed-root /path/to/safe/directory

# Use a different port
uv run filesystem-mcp --port 8000

# Combine options
uv run filesystem-mcp --allowed-root ~/projects --port 8000
```

### Command Line Options

- `--port <number>` - Port to listen on (default: 8123)
- `--allowed-root <path>` - Root directory for filesystem operations (default: current directory)

### Security Considerations

The `--allowed-root` parameter restricts all filesystem operations to the specified directory tree. Paths outside this directory will be rejected, even if accessed through symlinks or `..` path components.

**Important:** Always run the server with an appropriate `--allowed-root` to limit filesystem access. Never run with root privileges or system-critical directories as the allowed root.

## Available Tools

The server exposes 8 filesystem operation tools through the MCP protocol:

### 1. read_file

Read the contents of a file as text.

**Parameters:**
- `path` (string) - File path relative to allowed root

**Returns:** File contents as string

**Example:**
```json
{
  "name": "read_file",
  "arguments": {
    "path": "config.json"
  }
}
```

### 2. list_directory

List files and subdirectories in a directory with metadata.

**Parameters:**
- `path` (string, optional) - Directory path relative to allowed root (default: ".")

**Returns:** Formatted table with name, type, size, and modified time

**Example:**
```json
{
  "name": "list_directory",
  "arguments": {
    "path": "src"
  }
}
```

### 3. write_file

Create or overwrite a file with the given content.

**Parameters:**
- `path` (string) - File path relative to allowed root
- `content` (string) - Content to write to the file

**Returns:** Success message with character count

**Example:**
```json
{
  "name": "write_file",
  "arguments": {
    "path": "output.txt",
    "content": "Hello, World!"
  }
}
```

### 4. create_directory

Create a new directory, including parent directories if needed.

**Parameters:**
- `path` (string) - Directory path relative to allowed root

**Returns:** Success message

**Example:**
```json
{
  "name": "create_directory",
  "arguments": {
    "path": "logs/2024"
  }
}
```

### 5. delete_file

Delete a file.

**Parameters:**
- `path` (string) - File path relative to allowed root

**Returns:** Success message

**Example:**
```json
{
  "name": "delete_file",
  "arguments": {
    "path": "temp.txt"
  }
}
```

### 6. delete_directory

Delete a directory, optionally with all contents.

**Parameters:**
- `path` (string) - Directory path relative to allowed root
- `recursive` (boolean, optional) - Whether to delete non-empty directories (default: false)

**Returns:** Success message

**Example:**
```json
{
  "name": "delete_directory",
  "arguments": {
    "path": "old_logs",
    "recursive": true
  }
}
```

### 7. move_path

Move or rename a file or directory.

**Parameters:**
- `source` (string) - Source path relative to allowed root
- `destination` (string) - Destination path relative to allowed root

**Returns:** Success message

**Example:**
```json
{
  "name": "move_path",
  "arguments": {
    "source": "draft.txt",
    "destination": "final.txt"
  }
}
```

### 8. get_file_info

Get metadata about a file or directory.

**Parameters:**
- `path` (string) - Path relative to allowed root

**Returns:** Formatted metadata including size, modified/created times, permissions, and item count for directories

**Example:**
```json
{
  "name": "get_file_info",
  "arguments": {
    "path": "README.md"
  }
}
```

## Testing the Server

### Test with curl

```bash
# List available tools
curl -X POST http://localhost:8123/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'

# Initialize a session
curl -X POST http://localhost:8123/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    },
    "id": 1
  }'
```

### Test with MCP Client

You can use any MCP-compatible client to connect to the server. The server endpoint is:

```
http://localhost:8123/mcp
```

## Architecture

### Technology Stack

- **FastMCP** - High-level MCP framework with automatic Streamable HTTP support
- **uvicorn** - ASGI server for running the application
- **Python 3.12+** - Modern Python with type hints

### Project Structure

```
filesystem-mcp-server/
├── LICENSE                 # Apache 2.0 license
├── README.md              # This file
├── pyproject.toml         # Project metadata and dependencies
├── .python-version        # Python version specification
└── src/
    └── filesystem/
        ├── __init__.py    # Package initialization
        └── server.py      # Main server implementation
```

### Path Validation

All filesystem operations validate paths using a secure process:

1. Resolve the provided path relative to the allowed root
2. Canonicalize paths using `Path.resolve()` to resolve symlinks and `..` components
3. Verify the resolved path starts with the allowed root directory
4. Reject any path that escapes the allowed root

This prevents directory traversal attacks like `../../../etc/passwd`.

## Error Handling

The server provides clear error messages for common issues:

- **FileNotFoundError** - Requested file or directory doesn't exist
- **PermissionError** - Insufficient permissions for the operation
- **ValueError** - Invalid operation (e.g., trying to read a directory as a file)
- **UnicodeDecodeError** - Unable to decode file as text

All errors are returned as MCP error responses with descriptive messages.

## Development

### Running from Source

```bash
# Install dependencies
uv sync

# Run the server
uv run python -m filesystem.server --port 8123
```

### Building

```bash
# Build the package
uv build
```

## License

Apache License 2.0 - See LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:

- Code follows PEP 8 style guidelines
- All functions have type hints
- Error handling is comprehensive
- Security validations are maintained

## About MCP

This server implements the [Model Context Protocol](https://modelcontextprotocol.io/), an open protocol that enables seamless integration between LLM applications and external data sources and tools.

The server uses **Streamable HTTP transport**, the modern replacement for the deprecated HTTP+SSE transport as of MCP specification version 2025-03-26.
