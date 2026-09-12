---
name: transformers-descriptive
description: "Maintainer-documented descriptive knowledge for the huggingface/transformers repository: project structure, architecture, and facts."
---

# AGENTS.md Guide for Hugging Face Transformers

## Core Project Structure

- `/src/transformers`: This contains the core source code for the library
  - `/models`: Code for individual models. Models inherit from base classes in the root `/src/transformers` directory.
- `/tests`: This contains the core test classes for the library. These are usually inherited rather than directly run.
  - `/models`: Tests for individual models. Model tests inherit from common tests in the root `/tests` directory.
- `/docs`: This contains the documentation for the library, including guides, tutorials, and API references.

## Coding Conventions for Hugging Face Transformers

- Code style is enforced in the CI.

## Copying and inheritance

Many models in the codebase have similar code, but it is not shared by inheritance because we want each model file to be self-contained.
We use two mechanisms to keep this code in sync:

- "Copied from" syntax. Functions or entire classes can have a comment at the top like this: `# Copied from transformers.models.llama.modeling_llama.rotate_half` or `# Copied from transformers.models.t5.modeling_t5.T5LayerNorm with T5->MT5`
  These comments are actively checked by the style tools, and copies will automatically be updated when the base code is updated. If you need to update a copied function, you should
- "Modular" files. These files briefly define models by composing them using inheritance from other models. They are not meant to be used directly. Instead, the style tools
  automatically generate a complete modeling file, like `modeling_bert.py`, from the modular file like `modular_bert.py`. If a model has a modular file, the modeling file
