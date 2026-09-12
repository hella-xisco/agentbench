---
name: ansible-procedural
description: "Maintainer-documented procedural knowledge for the ansible/ansible repository: commands, workflows, and tool choices."
---

# AGENTS.md

## Quick Reference

```bash
# Testing
ansible-test sanity -v --docker default                    # Run all sanity tests
ansible-test sanity -v --docker default --test <test>     # Run specific sanity test
ansible-test units -v --docker default                    # Run unit tests
ansible-test integration -v --docker fedora42             # Run integration tests

# PR Review and CI
gh pr view <number>                                        # Get PR details
gh pr view <number> --comments                           # Check for ansibot CI failures
gh pr checks <number>                                     # Get Azure Pipelines URLs
gh pr checkout <number>                                   # Switch to PR branch
gh pr diff <number>                                       # See all changes
```

- Sanity/Unit tests: `--docker default`
- Integration tests: `--docker fedora42`, `--docker ubuntu2204`, etc. (NOT default/base)

## Development Environment Setup

Ansible development typically uses an editable install after forking and cloning:

```bash
# After forking and cloning the repository
pip install -e .
```

## Testing and CI

### Basic Testing Commands

```bash
ansible-test sanity -v --docker default

# List available sanity tests
ansible-test sanity --list-tests

# Run specific sanity tests
ansible-test sanity -v --docker default --test pep8 --test pylint

# Run sanity on specific files (paths relative to repo root)
ansible-test sanity -v --docker default lib/ansible/modules/command.py

# Run unit tests (recommended with Docker)
ansible-test units -v --docker default

# Run specific unit test (paths relative to repo root, targets in test/units/)
ansible-test units -v --docker default test/units/modules/test_command.py

# Run integration tests (choose appropriate container - NOT base/default)
ansible-test integration -v --docker fedora42

# Run specific integration target (directory name in test/integration/targets/)
ansible-test integration -v --docker ubuntu2204 setup_remote_tmp_dir

# Run with coverage
ansible-test units -v --docker default --coverage

# Alternative: use --venv if Docker/Podman unavailable (less reliable for units/integration)
ansible-test sanity -v --venv
```

The `base` and `default` containers are for sanity/unit tests only. For integration tests, use distro-specific
containers like `fedora42`, `ubuntu2204`, `ubuntu2404`, `alpine322` depending on the modules being tested.

- `--docker` (supports Docker or Podman) - preferred for reliable, isolated testing
- `--venv` - fallback when containers unavailable, but unit tests may be unreliable due to host environment differences

### Helping Developers with CI Failures

```bash
# Get all PR comments to find ansibot CI failure reports
gh pr view <number> --comments
```

Look for comments from `ansibot` that contain:
- Test failure details with specific error messages
- File paths and line numbers for failures
- Links to sanity test documentation (e.g., `[explain](https://docs.ansible.com/...`)

**2. Get CI check status and URLs:**

```bash
# See all CI check results with Azure Pipelines URLs
gh pr checks <number>
```

**4. CI failure analysis workflow:**

1. Check ansibot comments first for immediate error details
2. Use `gh pr checks <number>` to get Azure Pipelines URLs for detailed logs
3. Focus on failed jobs (marked as `fail`) and examine their specific error output
4. For sanity test failures, the error messages usually indicate exactly what needs to be fixed
5. For test failures, run the same tests locally using `ansible-test` to reproduce and debug

## PR Review Guidelines

### PR Review Checklist

Use this checklist for EVERY PR review:

```text
□ Created TodoWrite list for review steps
□ Step 1: Get PR details with gh pr view <number>
□ Step 2: Get PR diff with gh pr diff <number>
□ Step 3: Check required components (changelog, tests)
□ Step 4: Checkout PR branch with gh pr checkout <number>
□ Step 5: Review existing feedback with gh pr view <number> --comments
□ Step 6: Verify all issues addressed
□ Step 7: Call out any unresolved feedback
□ Mark each TodoWrite item as completed when done
```

When assisting with PR reviews, verify:

### Review Tools

- `Read` tool - Examine specific changed files in detail
- `Grep` tool - Search for related code patterns or test coverage (uses ripgrep/rg)

## Development Guidelines

### Code Style Notes

- In `lib/ansible/modules/`, imports must come after DOCUMENTATION, EXAMPLES, and RETURN definitions
- Use native type hints with `from __future__ import annotations` (converts to strings at runtime)

### Dependencies and Imports

- Prefer Python stdlib over external dependencies
- `lib/ansible/modules/` can only import from `lib/ansible/module_utils/` (modules are packaged for remote execution)
- `lib/ansible/module_utils/` cannot import from outside itself

## Documentation Standards

### Module and Plugin Documentation

- Modules and plugins require DOCUMENTATION, EXAMPLES, and RETURN blocks as static YAML string variables
- All modules should have a `main()` function and `if __name__ == '__main__':` block

## Repository Management

### Backwards Compatibility

- Use `Display.deprecated` or `AnsibleModule.deprecate` with version from `lib/ansible/release.py` plus 3
