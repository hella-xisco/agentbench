# AGENTS Instruction

The main developer documentation for Wagtail lives in the `docs/contributing` directory.

## Wagtail-specific pitfalls for AI agents

### StreamField and StreamBlock template access

- Wagtail's StreamBlock and StreamField use the same template syntax, but they differ from standard Django field access.
