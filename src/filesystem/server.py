"""Filesystem MCP Server with Streamable HTTP support."""

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="filesystem",
    json_response=False,
    stateless_http=False,
)

ALLOWED_ROOT: Path | None = None


def validate_path(relative_path: str) -> Path:
    """Validate and resolve a path against the allowed root directory.

    Args:
        relative_path: Path relative to the allowed root

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is outside allowed root or ALLOWED_ROOT not set
    """
    if ALLOWED_ROOT is None:
        raise ValueError("Server not properly initialized: ALLOWED_ROOT not set")

    full_path = ALLOWED_ROOT / relative_path
    resolved = full_path.resolve()
    allowed = ALLOWED_ROOT.resolve()

    if not str(resolved).startswith(str(allowed)):
        raise ValueError(f"Path '{relative_path}' is outside allowed root directory")

    return resolved


@mcp.tool()
async def read_file(path: str) -> str:
    """Read the contents of a file as text.

    Args:
        path: File path relative to allowed root

    Returns:
        File contents as string
    """
    validated_path = validate_path(path)

    if not validated_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not validated_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    try:
        return validated_path.read_text()
    except UnicodeDecodeError as e:
        raise ValueError(f"Unable to decode file as text: {e}")
    except PermissionError:
        raise PermissionError(f"Permission denied reading file: {path}")


@mcp.tool()
async def list_directory(path: str = ".") -> str:
    """List files and subdirectories in a directory.

    Args:
        path: Directory path relative to allowed root (default: current directory)

    Returns:
        Formatted string with directory contents including metadata
    """
    validated_path = validate_path(path)

    if not validated_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not validated_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    try:
        entries = []
        for item in sorted(validated_path.iterdir()):
            stat = item.stat()
            entry_type = "dir" if item.is_dir() else "file"
            size = stat.st_size if item.is_file() else 0
            modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

            entries.append(f"{item.name:<40} {entry_type:<6} {size:>12} bytes  {modified}")

        if not entries:
            return f"Directory '{path}' is empty"

        header = f"{'Name':<40} {'Type':<6} {'Size':>12}        {'Modified'}"
        separator = "-" * 80
        return f"{header}\n{separator}\n" + "\n".join(entries)
    except PermissionError:
        raise PermissionError(f"Permission denied accessing directory: {path}")


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content.

    Args:
        path: File path relative to allowed root
        content: Content to write to the file

    Returns:
        Success message
    """
    validated_path = validate_path(path)

    if validated_path.exists() and not validated_path.is_file():
        raise ValueError(f"Path exists but is not a file: {path}")

    if not validated_path.parent.exists():
        raise ValueError(f"Parent directory does not exist: {validated_path.parent}")

    try:
        validated_path.write_text(content)
        return f"Successfully wrote {len(content)} characters to '{path}'"
    except PermissionError:
        raise PermissionError(f"Permission denied writing to file: {path}")


@mcp.tool()
async def create_directory(path: str) -> str:
    """Create a new directory, including parent directories if needed.

    Args:
        path: Directory path relative to allowed root

    Returns:
        Success message
    """
    validated_path = validate_path(path)

    if validated_path.exists():
        if validated_path.is_dir():
            return f"Directory already exists: {path}"
        else:
            raise ValueError(f"Path exists but is not a directory: {path}")

    try:
        validated_path.mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory: {path}"
    except PermissionError:
        raise PermissionError(f"Permission denied creating directory: {path}")


@mcp.tool()
async def delete_file(path: str) -> str:
    """Delete a file.

    Args:
        path: File path relative to allowed root

    Returns:
        Success message
    """
    validated_path = validate_path(path)

    if not validated_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not validated_path.is_file():
        raise ValueError(f"Path is not a file (use delete_directory for directories): {path}")

    try:
        validated_path.unlink()
        return f"Successfully deleted file: {path}"
    except PermissionError:
        raise PermissionError(f"Permission denied deleting file: {path}")


@mcp.tool()
async def delete_directory(path: str, recursive: bool = False) -> str:
    """Delete a directory.

    Args:
        path: Directory path relative to allowed root
        recursive: Whether to delete non-empty directories (default: False)

    Returns:
        Success message
    """
    validated_path = validate_path(path)

    if not validated_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not validated_path.is_dir():
        raise ValueError(f"Path is not a directory (use delete_file for files): {path}")

    try:
        if recursive:
            shutil.rmtree(validated_path)
            return f"Successfully deleted directory and contents: {path}"
        else:
            validated_path.rmdir()
            return f"Successfully deleted empty directory: {path}"
    except OSError as e:
        if "not empty" in str(e).lower():
            raise ValueError(f"Directory not empty (use recursive=true to delete): {path}")
        raise PermissionError(f"Permission denied deleting directory: {path}")


@mcp.tool()
async def move_path(source: str, destination: str) -> str:
    """Move or rename a file or directory.

    Args:
        source: Source path relative to allowed root
        destination: Destination path relative to allowed root

    Returns:
        Success message
    """
    validated_source = validate_path(source)
    validated_dest = validate_path(destination)

    if not validated_source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if validated_dest.exists():
        raise ValueError(f"Destination already exists: {destination}")

    if not validated_dest.parent.exists():
        raise ValueError(f"Destination parent directory does not exist: {validated_dest.parent}")

    try:
        validated_source.rename(validated_dest)
        item_type = "directory" if validated_dest.is_dir() else "file"
        return f"Successfully moved {item_type} from '{source}' to '{destination}'"
    except PermissionError:
        raise PermissionError(f"Permission denied moving from '{source}' to '{destination}'")


@mcp.tool()
async def get_file_info(path: str) -> str:
    """Get metadata about a file or directory.

    Args:
        path: Path relative to allowed root

    Returns:
        Formatted string with file metadata
    """
    validated_path = validate_path(path)

    if not validated_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    try:
        stat = validated_path.stat()

        is_dir = validated_path.is_dir()
        is_file = validated_path.is_file()
        size = stat.st_size if is_file else 0
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
        created = datetime.fromtimestamp(stat.st_ctime).isoformat()

        info_lines = [
            f"Path: {path}",
            f"Type: {'Directory' if is_dir else 'File'}",
            f"Size: {size:,} bytes" if is_file else "Size: N/A (directory)",
            f"Modified: {modified}",
            f"Created: {created}",
            f"Permissions: {oct(stat.st_mode)[-3:]}",
        ]

        if is_dir:
            item_count = len(list(validated_path.iterdir()))
            info_lines.append(f"Items: {item_count}")

        return "\n".join(info_lines)
    except PermissionError:
        raise PermissionError(f"Permission denied accessing path: {path}")


def main() -> None:
    """Main entry point for the filesystem MCP server."""
    parser = argparse.ArgumentParser(
        description="Filesystem MCP Server with Streamable HTTP support"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8123,
        help="Port to listen on (default: 8123)",
    )
    parser.add_argument(
        "--allowed-root",
        type=str,
        default=".",
        help="Root directory for filesystem operations (default: current directory)",
    )
    args = parser.parse_args()

    global ALLOWED_ROOT
    ALLOWED_ROOT = Path(args.allowed_root).resolve()

    if not ALLOWED_ROOT.exists():
        print(f"Error: Allowed root directory does not exist: {ALLOWED_ROOT}")
        exit(1)

    if not ALLOWED_ROOT.is_dir():
        print(f"Error: Allowed root is not a directory: {ALLOWED_ROOT}")
        exit(1)

    print(f"Starting Filesystem MCP Server")
    print(f"Allowed root: {ALLOWED_ROOT}")
    print(f"Listening on: http://localhost:{args.port}/mcp")

    uvicorn.run(mcp.streamable_http_app, host="localhost", port=args.port)


if __name__ == "__main__":
    main()
