---
name: transformers-procedural
description: "Maintainer-documented procedural knowledge for the huggingface/transformers repository: commands, workflows, and tool choices."
---

# AGENTS.md Guide for Hugging Face Transformers

## Coding Conventions for Hugging Face Transformers

- PRs should be as brief as possible. Bugfix PRs in particular can often be only one or two lines long, and do not need large comments, docstrings or new functions in this case. Aim to minimize the size of the diff.
- When writing tests, they should be added to an existing file. The only exception is for PRs to add a new model, when a new test directory should be created for that model.
- You can install the style tools with `pip install -e .[quality]`. … You can then run `make fixup` to apply style and consistency fixes to your code.

## Copying and inheritance

  either update the base function and use `make fixup` to propagate the change to all copies, or simply remove the `# Copied from` comment if that is inappropriate.
  should never be edited directly! Instead, changes should be made in the modular file, and then you should run `make fixup` to update the modeling file automatically.

When adding new models, you should prefer `modular` style.

## Testing

After making changes, you should usually run `make fixup` to ensure any copies and modular files are updated, and then test all affected models. This includes both
the model you made the changes in and any other models that were updated by `make fixup`. Tests can be run with `pytest tests/models/[name]/test_modeling_[name].py`
If your changes affect code in other classes like tokenizers or processors, you should run those tests instead, like `test_processing_[name].py` or `test_tokenization_[name].py`.

In order to run tests, you may need to install dependencies. You can do this with `pip install -e .[testing]`. You will probably also need to `pip install torch accelerate` if your environment does not already have them.
