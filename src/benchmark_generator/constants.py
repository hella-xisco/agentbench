from __future__ import annotations

import textwrap

# Shared prompt templates for the various benchmark generator agents.
REPO_FILTERING_TEMPLATE = textwrap.dedent(
    """
    Your goal is to filter GitHub repositories to identify those suitable for generating regression-test, and if suitable generate a docker image setup for them.

    A repository is suitable if setting it up does not require human intervention, it does not require external accounts (e.g., cloud provider accounts, API keys, ...) or payments to function, and it uses standard package managers and build tools. What I want is to be able to run the tests in an automated way in a clean environment.

    Deliverables:
    1. Create the JSON file {decision_path} with UTF-8 encoded content describing your
       decision using this schema:
       {{
         "repo_full_name": "<owner/repo>",
         "suitable": <bool>,
         "rationale": "<short explanation>"
       }}
       - Set "suitable" to true only when you are confident the repository can be set up and its tests run in an automated way without human intervention.
    2. If suitable is true, also create a Dockerfile at the root of the repository that allows to build a docker image that sets up the environment to run the tests. You should use Dockerfile_template as a base template. In particular, make sure that the repo is cloned in /testbed and that the WORKDIR is set to /testbed.
    """
).strip()

TRIAGE_PROMPT_TEMPLATE = textwrap.dedent(
    """
    You are evaluating pull request #{pr_number} for suitability as a regression-test
    task in SWE-bench style datasets. Decide whether the PR primarily introduces deterministic, testable behaviour.
    Such behaviors typically include bug fixes, but can also include feature additions as long as it is possible to write a precise specification that allows testing the new feature independently of the implementation.

    Repository: {repo_full_name}
    Title: {title}
    Author: {author}
    Merged at: {merged_at}

    PR description:
    {body}

    Diff excerpt:
    {excerpt}

    Deliverables:
    1. Do NOT modify existing project code.
    2. Create the JSON file {decision_path} with UTF-8 encoded content describing your
       decision using this schema:
       {{
         "pr_number": <int>,
         "suitable": <bool>,
         "needs_manual_review": <bool>,
         "decision": "include" | "exclude" | "manual_review",
         "rationale": "<short explanation>",
         "key_files": ["relative/file.py", "..."],
         "risk_factors": ["<short string>", "..."]
       }}
       - Set "decision" to "include" only when you are confident the PR is a self-contained
         bug fix that can be validated via regression tests.
       - Use "manual_review" if you are uncertain.
    3. Stage the JSON file and finish. Do not stage anything else.
    """
).strip()

SETUP_AGENT_PROMPT_TEMPLATE = textwrap.dedent(
    """
    Your goal is to help developers set up their environment to run code in the repository and be able to run the current tests. You should write a list of all commands needed to (i) setup the environment from scratch, and (ii) run the existing tests. You need to make sure that the commands you provide actually work for you. The setup is considered valid if most of the tests are passing after running **exactly** your setup commands and the test commands you provide.

    In particular, for running the repo tests you should create a file at the root of the repository called `run_tests.py` that executes all the tests, parses the output of the tests and returns the test results in JSON format with the following schema:
    {{"test_name": <bool>, ...}} where each test_name is the name of a test and the bool indicates whether the test passed (true) or failed (false). This JSON file should be saved by the script at the root of the repository as `test_results.json`.

    Deliverables:
    1. Create the JSON file {decision_path} with UTF-8 encoded content explaining the steps to setup the environment and run the tests (using the `run_tests.py` script you created):
       {{
         "setup_commands": ["<command1>", "<command2>", "..."],
         "test_commands": ["<command1>", "<command2>", "..."] 
       }}
    2. Create the script `run_tests.py` at the root of the repository.
    3. Stage the JSON file and the script and finish. Do not stage anything else.

    {example_files_section}
    """
).strip()

STATEMENT_GENERATION_PROMPT_TEMPLATE = textwrap.dedent(
    """
    You are given a pull request (PR) and the related issues for a given GitHub repository.
    Your goal is to format this information into a (clear) Github Issue following the template below. In particular, for the steps to reproduce fields, only write the steps you actually took to reproduce the issue in your specific environment. Make sure those steps are reproducible and minimal.
    Given your issue, developers should be able to implement a solution similar to the one provided in the PR; but your Issue should not leak the solution.
    You should save your output in markdown format in the file {metadata_relpath}.

    Additionally, for issue that are about adding a new feature rather than fixing a bug, you need to provide a very prcise specification of the desired behavior in the "Specification" field. This specification should be detailed enough to allow for independent testing of the new feature without relying on implementation details from the PR. For instance, if I have a class foo and I want to add a method bar to it, I need to specify exactly what bar should do, what inputs it should take (including the types and possible edge cases), what outputs it should produce, and any side effects it may have. In the end, any test written based on this specification should be able to determine whether the feature has been correctly implemented according to the specification, without any knowledge of how it was implemented in the PR. At the same time, the patch provided in the PR should be sufficient to implement the feature as specified. If the PR contains human readable outputs (e.g., log messages, UI text, eroor messages, ...), you should include them in the specification and explicitly state that any fix must use **exactly** those error messages.

    Below is the template for the Github Issue:
    ```
    ### Description  
    (Provide a clear and concise description of the problem.)  

    ### Steps to Reproduce  
    1. [Step 1]  
    2. [Step 2]  
    3. ...

    ### Expected Behavior (if applicable) 
    (Explain what you expected to happen.)  

    ### Actual Behavior (if applicable) 
    (Explain what actually happened.)  

    ### Specification (if applicable)  
    (Provide a precise specification of the desired behavior.)

    ### Additional Information  
    (Add screenshots, logs, or other helpful details.)  
    ```

    # Data for PR #{pr_number} in repository {repo} at commit {commit_sha}

    PR description:
    {pr_description}

    Referenced issues mentioned in the PR:
    {referenced_issues_text}

    PR patch:
    {pr_patch}

    PR test (if any):
    {pr_test_patch}

    Key files identified during triage:
    {key_files_text}
    """
).strip()


INSTANCE_GENERATION_PROMPT_TEMPLATE = textwrap.dedent(
    """
    You are generating regression tests for pull request #{pr_number} in {repo}.
    The current checkout is the base (pre-fix) commit {commit_sha}.

    Problem description:
    {problem_description}

    PR patch:
    {pr_patch}

    PR test (if any):
    {pr_test_patch}

    Requirements:
    1. Focus on deterministic tests that expose the bug fixed by this PR. Your tests should focus on the exected behavior and not use any internal details (variables, hidden functions, etc...). They should fail on the base commit and pass on the merge commit (after applying the PR patch). You need to make sure this property is verified. To do so, you can apply the provided pr patch using `git apply`. If there is a specification provided in the problem description, your tests must exactly align with it. In particular, do not write tests that are using implementation details that are not part of the specification. Also, make sure your tests are robust to variations in how one might implement the fix (e.g., do not rely on specific variable names, function names, specific strings, ... unless explicitly mentioned in the specification).

    2. For running your proposed tests you should create a file at the root of the repository called `run_pr_tests.py` that executes all the tests you created, parses the output of the tests and returns the test results in JSON format with the following schema:
    {{"test_name": <bool>, ...}} where each test_name is the name of a test and the bool indicates whether the test passed (true) or failed (false). This JSON file should be saved by the script at the root of the repository as `pr_test_results.json`. You can look at the `run_tests.py` script to have an example of how to write such a script. Note that your script should only run the tests you created for this PR.

    3. Ensure your new tests match the project's existing test style and conventions. You may re-use the test from the PR if appropriate. You should always first look at all existing tests to understand the structure and framework used. 

    4. All the new tests you create must be in new files that you create as part of this PR. Do NOT modify any existing test files (even if they are related).

    5. For the test_commands, make sure to include any necessary steps (like sourcing virtual environments, setting environment variables, etc...) to ensure the tests run correctly in a fresh shell.
    
    Deliverables:
    1. Create the new test files with your proposed tests.
    2. Create the JSON file {metadata_relpath} with UTF-8 explaining how to run tests:
      {{
         "test_commands": ["<command1>", "<command2>", "..."], # Commands to run the PR tests with `run_pr_tests.py`
         "test_files": ["path/to/test_file1", "path/to/test_file2", "..."]
       }}
    3. Create the script `run_pr_tests.py` at the root of the repository.
    4. Stage the JSON file and the script and finish. Do not stage anything else.
    """
).strip()


