---
name: fastmcp-procedural
description: "Maintainer-documented procedural knowledge for the jlowin/fastmcp repository: commands, workflows, and tool choices."
---

# FastMCP Development Guidelines

## Required Development Workflow

**CRITICAL**: Always run these commands in sequence before committing:

```bash
uv sync                              # Install dependencies
uv run prek run --all-files          # Ruff + Prettier + ty
uv run pytest -n auto                # Run full test suite
```

Alternative: `just build && just typecheck && just test`

## Core MCP Objects

When modifying MCP functionality, changes typically need to be applied across all object types:

- **Tools** (`src/tools/` + `ToolManager`)
- **Resources** (`src/resources/` + `ResourceManager`)
- **Resource Templates** (`src/resources/` + `ResourceManager`)
- **Prompts** (`src/prompts/` + `PromptManager`)

## Testing Best Practices

### Testing Standards

- **NEVER** add `@pytest.mark.asyncio` to tests - `asyncio_mode = "auto"` is set globally
- **ALWAYS** run pytest after significant changes

### Inline Snapshots

when running `pytest --inline-snapshot=create`. To update snapshots after intentional changes, run `pytest --inline-snapshot=fix`.

### Always Use In-Memory Transport

Pass FastMCP servers directly to clients for testing:

```python
mcp = FastMCP("TestServer")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

# Direct connection - no network complexity
async with Client(mcp) as client:
    result = await client.call_tool("greet", {"name": "World"})
```

Only use HTTP transport when explicitly testing network features:

```python
# Network testing only
async with Client(transport=StreamableHttpTransport(server_url)) as client:
    result = await client.ping()
```

## Development Rules

### Documentation

- Never modify `docs/python-sdk/**` (auto-generated)

## Key Tools & Commands

### Environment Setup

```bash
git clone <repo>
cd fastmcp
uv sync                    # Installs all deps including dev tools
```

### Validation Commands (Run Frequently)

- **Linting**: `uv run ruff check` (or with `--fix`)
- **Type Checking**: `uv run ty check`
- **All Checks**: `uv run prek run --all-files`

### Testing

- **Standard**: `uv run pytest -n auto`
- **Integration**: `uv run pytest -n auto -m "integration"`
- **Excluding markers**: `uv run pytest -n auto -m "not integration and not client_process"`

### CLI Usage

- **Run server**: `uv run fastmcp run server.py`
- **Inspect server**: `uv run fastmcp inspect server.py`

## Critical Patterns

### Error Handling

- Never use bare `except` - be specific with exception types

### Build Issues (Common Solutions)

1. **Dependencies**: Always `uv sync` first
2. **Prek fails**: Run `uv run prek run --all-files` to see failures
3. **Type errors**: Use `uv run ty check` directly, check `pyproject.toml` config
4. **Test timeouts**: Default 5s - optimize or mark as integration tests
