---
name: wagtail-procedural
description: "Maintainer-documented procedural knowledge for the wagtail/wagtail repository: commands, workflows, and tool choices."
---

# AGENTS Instruction

## Wagtail-specific pitfalls for AI agents

### StreamField and StreamBlock template access

- When you use StreamField and other custom block types in Wagtail templates, you usually need to use the value property in your data variables.
