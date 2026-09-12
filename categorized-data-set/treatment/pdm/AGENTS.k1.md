# CLAUDE.md

## Development Commands

### Setup Development Environment
```bash
# Install development dependencies
pdm install
```

### Run Tests
```bash
# Run all tests
pdm run test

# Run tests in parallel
pdm run test -n auto
```

Most of the time, you can exclude tests with "integration" mark to save runtime:

```bash
pdm run test -n auto -m "not integration"
```

### Code Quality
```bash
# Run linting (ruff-format + codespell + mypy)
pdm run lint
```

### Documentation
```bash
# Serve documentation locally
pdm run doc
```

### Release Process
```bash
# Preview changelog
pdm run release --dry-run

# Create release
pdm run release
```

## Common Development Tasks

### Adding a New Command
1. Create new file in `src/pdm/cli/commands/`
2. Inherit from `BaseCommand`
3. Register in `src/pdm/core.py`

### Debugging Resolution Issues
- Set `PDM_DEBUG=1` environment variable for verbose output
- Check `pdm.lock` for resolved versions
- Use `pdm lock --check` to verify lock file

### Update dependencies

```bash
# Add a new dependency to default group
pdm add <package_name>

# Update all dependencies
pdm update

# Remove a dependency
pdm remove <package_name>

# Add a new dependency to given group
pdm add <package_name> --group <group_name>
```
