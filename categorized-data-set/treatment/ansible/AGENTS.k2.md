# AGENTS.md

## ⚠️ CRITICAL: Licensing Requirements

- **lib/ansible/module_utils/**: Defaults to **BSD-2-Clause** (more permissive)

## Development Environment Setup

**Note:** ansible-core and all CLIs (including ansible-test) require a POSIX OS. On Windows, use WSL (Windows Subsystem for Linux).

## Testing and CI

### Basic Testing Commands

```bash
# Run sanity tests - these are linting/static analysis (pylint, mypy, pep8, etc.)

```

Available Docker containers for testing can be found in `./test/lib/ansible_test/_data/completion/docker.txt`.

### Helping Developers with CI Failures

This shows:
- Overall CI status (pass/fail) with timing
- Direct links to Azure DevOps build results
- Individual job results (Sanity Test 1/2, Docker tests, Units, etc.)

**3. Common CI failure patterns:**

- **Sanity failures**: Usually have specific fixes (trailing whitespace, import errors, etc.)
- **Integration test failures**: May require platform-specific containers or test adjustments
- **Unit test failures**: Often indicate actual code issues that need debugging

## Development Guidelines

### Python Version Support

- Controller code: support range defined in `pyproject.toml`
- Modules/module_utils: minimum version in `lib/ansible/module_utils/basic.py` (`_PY_MIN`) up to max from `pyproject.toml`
- Modules support a wider Python version range than controller code

## Documentation Standards

### Module and Plugin Documentation

- These blocks cannot be dynamically generated - they are parsed via AST/token parsing
- Alternative: "sidecar" documentation as `.yml` files with same stem name adjacent to plugin files

## Code Structure Reference

### Core Structure

- `lib/ansible/` - Main Ansible library code
  - `cli/` - Command-line interface implementations (ansible, ansible-playbook, etc.)
  - `executor/` - Task execution engine and strategies (includes PowerShell support in `powershell/`)
  - `inventory/` - Inventory management and parsing
  - `modules/` - Core modules (built-in automation modules)
  - `module_utils/` - Shared utilities for modules (includes C# in `csharp/` and PowerShell in `powershell/`)
  - `plugins/` - Plugin framework (filters, tests, lookups, etc.)
  - `vars/` - Variable management
  - `config/` - Configuration handling
  - `collections/` - Ansible Collections framework

### Key Components

- **CLI Layer**: Entry points in `lib/ansible/cli/` handle command parsing and dispatch
- **Executor**: `lib/ansible/executor/` contains the core execution engine that runs tasks and plays
- **Module System**: Modules in `lib/ansible/modules/` are the units of work; they're executed remotely
- **Plugin Architecture**: `lib/ansible/plugins/` provides extensibility through filters, tests, lookups, etc.
- **Inventory**: `lib/ansible/inventory/` manages host and group definitions
- **Collections**: Modern packaging format for distributing Ansible content

### Testing Infrastructure

- `test/units/` - Unit tests mirroring the lib structure
- `test/integration/` - Integration tests organized by target (named after plugin/functionality being tested)
  - Some targets have `context/controller` or `context/target` in their `aliases` file when not easily inferable
  - Only modules run on target hosts; all other plugins execute locally in the ansible process
- `test/lib/` - Test utilities and frameworks
- `ansible-test` - Unified testing tool for all test types
