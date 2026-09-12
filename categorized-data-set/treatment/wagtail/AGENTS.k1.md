# AGENTS Instruction

## Wagtail-specific pitfalls for AI agents

### StreamField and StreamBlock template access

- When you use StreamField and other custom block types in Wagtail templates, you usually need to use the value property in your data variables.
