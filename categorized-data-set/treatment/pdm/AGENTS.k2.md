# CLAUDE.md

## Project Overview

PDM (Python Dependency Manager) is a modern Python package and dependency manager that supports the latest PEP standards (PEP 517, PEP 621). It provides fast dependency resolution, flexible plugin system, and centralized cache management similar to pnpm.

## Core Architecture

### Key Components

1. **Project Management** (`src/pdm/project/`): Handles pyproject.toml parsing, project configuration, and metadata management
2. **Dependency Resolution** (`src/pdm/resolver/`): Fast dependency resolver using resolvelib with custom optimizations for binary distributions
3. **Environment Management** (`src/pdm/environments/`): Manages Python environments (virtualenv, PEP 582, system)
4. **Installer System** (`src/pdm/installers/`): Installs packages using pbs-installer with centralized cache support
5. **CLI System** (`src/pdm/cli/commands/`): Command-line interface using argparse with plugin support
6. **Repository Models** (`src/pdm/models/repositories/`): PyPI repository interaction and package finder
7. **Build System** (`src/pdm/builders/`): PEP 517 build backend for creating wheels and sdists

### Command Entry Points

All CLI commands are in `src/pdm/cli/commands/` with command registration in `src/pdm/core.py`. Commands inherit from `BaseCommand` and use decorator patterns for common options.

## Testing Guidelines

Tests are in the `tests/` directory organized by module. Key test fixtures:
- `project` fixture: Creates temporary PDM projects
- `working_set` fixture: Mock Python environment
- `repository` fixture: Mock PyPI repository

Tests use pytest with pytest-mock for mocking and pytest-httpserver for HTTP testing.

## Important Files

- `pyproject.toml`: Project configuration and dependencies
- `src/pdm/core.py`: Main application entry point and command registration
- `src/pdm/project/__init__.py`: Project class managing project state
- `src/pdm/cli/commands/base.py`: Base command class for all CLI commands
- `.pre-commit-config.yaml`: Code quality hooks (ruff, mypy, codespell)

## Common Development Tasks

### Working with Lock Files

PDM uses its own lock file format (`pdm.lock`) that includes:
- Exact versions with hashes
- Environment markers
- Cross-platform support
- Group dependencies

## Architecture Patterns

- **Dependency Injection**: Core class passed to commands
- **Signal System**: Event-driven architecture for plugins
- **Repository Pattern**: Abstract repository interface for package sources
- **Strategy Pattern**: Different environment backends (venv, conda, etc.)
- **Chain of Responsibility**: Middleware system for HTTP client
