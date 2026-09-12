# FastMCP Development Guidelines

FastMCP is a comprehensive Python framework (Python ≥3.10) for building Model Context Protocol (MCP) servers and clients. This is the actively maintained v2.0 providing a complete toolkit for the MCP ecosystem.

## Required Development Workflow

All three must pass - this is enforced by CI.

## Repository Structure

| Path               | Purpose                                                                             |
| ------------------ | ----------------------------------------------------------------------------------- |
| `src/fastmcp/`     | Library source code (Python ≥ 3.10)                                                 |
| `├─server/`        | Server implementation, `FastMCP`, auth, networking                                  |
| `│  ├─auth/`       | Authentication providers (Google, GitHub, Azure, AWS, WorkOS, Auth0, JWT, and more) |
| `│  └─middleware/` | Error handling, logging, rate limiting                                              |
| `├─client/`        | High-level client SDK + transports                                                  |
| `│  └─auth/`       | Client authentication (Bearer, OAuth)                                               |
| `├─tools/`         | Tool implementations + `ToolManager`                                                |
| `├─resources/`     | Resources, templates + `ResourceManager`                                            |
| `├─prompts/`       | Prompt templates + `PromptManager`                                                  |
| `├─cli/`           | FastMCP CLI commands (`run`, `dev`, `install`)                                      |
| `├─contrib/`       | Community contributions (bulk caller, mixins)                                       |
| `├─experimental/`  | Experimental features (sampling handlers)                                           |
| `└─utilities/`     | Shared utilities (logging, JSON schema, HTTP)                                       |
| `tests/`           | Comprehensive pytest suite with markers                                             |
| `docs/`            | Mintlify documentation (published to gofastmcp.com)                                 |
| `examples/`        | Runnable demo servers (echo, smart_home, atproto)                                   |

## Testing Best Practices

### Inline Snapshots

FastMCP uses `inline-snapshot` for testing complex data structures. On first run with empty `snapshot()`, pytest will auto-populate the expected value … This is particularly useful for testing JSON schemas and API responses.

## Development Rules

### Git & CI

- Prek hooks are required (run automatically on commits)

### Code Standards

- Python ≥ 3.10

### Documentation

- Uses Mintlify framework
- Files must be in docs.json to be included
