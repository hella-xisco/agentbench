# Adapted to fit the AGENTS.md format
GENERATOR_PROMPT = """Here are some repo-specific and general experiences you could refer to when you try to solve the user's issue.

{experience}
"""

SUMMARIZER_PROMPT = """You are an advanced reasoning agent that can add, edit or remove rules from your existing rule set, based on forming new critiques of past task trajectories. You will be given a task trial in which you were given an issue and tried to reproduce it. You can also refer to the Golden Test Patch, which provides unit test code for this issue. It is meant to help you identify the reason for the reproduction failure and to gain insights. Pay special attention to this step when the model determines that the reproduction task has failed, but do not follow its format.

Repository: {repo}
Issue: {issue}
Trajectory: {trajectory}
Golden Test Patch: {golden_test_patch}

Remember that your task is to replicate the problem code from the issue. Therefore, when summarizing your experiences later, please carefully compare the issue with the Golden Test Patch. Analyze why you were unable to successfully reproduce the errors that occurred in the issue, rather than focusing on why the code in the issue was written incorrectly.

Here are the EXISTING RULES:
{previous_exp}

By examining the successful trials, and the list of existing rules, you can perform the following operations: add, edit, remove, or agree or merge so that the new list of rules are general and high level insights of the successful trials or proposed way of Thought so they can be used as helpful tips to different tasks in the future. Have an emphasis on tips that help the agent perform better Thought and Action. Follow the below format:

<OPERATION> <RULE NUMBER>: <RULE>

The available operations are: 
AGREE: Use this option if the existing rule is applicable in the successful trial.
REMOVE: Select this option if an existing rule is contradictory to others or if it is similar or duplicate to another rule. Please provide the corresponding text of the rule that you want to remove.
ADD: Choose this option to introduce new rules that are significantly different from existing ones and relevant to other tasks. Alternatively, if you encounter an unsolvable issue, you can add a new rule that describes the problem, such as noting that during xxx, you will face the xxx issue.
EDIT: Opt for this if an existing rule lacks generality or could be improved. Rewrite it to enhance clarity. If some previously unsolvable issues were resolved in this trial, please update the experience to indicate that when encountering the xxx problem, one should xxxx modify it. Do not change to an existing rule.
MERGE: Use this option to combine two similar existing rules into a single, cohesive rule.

Each needs to CLOSELY follow their corresponding formatting below (any existing rule not edited, not agreed, nor removed is considered copied):

AGREE <EXISTING RULE NUMBER>: <EXISTING RULE>
REMOVE <EXISTING RULE NUMBER>: <EXISTING RULE>
EDIT <EXISTING RULE NUMBER>: <NEW MODIFIED RULE>
ADD <NEW RULE NUMBER>: <NEW RULE>
MERGE <EXISTING RULE NUMBER1> <EXISTING RULE NUMBER2>: <NEW RULE>


Do not mention the trials in the rules because all the rules should be GENERALLY APPLICABLE or specially for this repo. Each rule should be concise and easy to follow. Any operation can be used MULTIPLE times. You can ONLY perform at most 4 operations, and each existing rule can only receive a maximum of 1 operation. You need to output in the following format:

<all_repo_rules>
1. ADD or EDIT or REMOVE or AGREE or MERGE ...
2. ...
</all_repo_rules>

<{repo}_rules>
1. ADD or EDIT or REMOVE or AGREE or MERGE ...
2. ...
</{repo}_rules>

If you think this experience is applicable to all repositories, write in <all_repo_rules> </all_repo_rules>.
If this experience is only applicable to the {repo} repository, write in <{repo}_rules> </{repo}_rules>.
Note that the content in the two parts should NOT have any repetitions.
If the length of EXISTING RULES is greater than 10, you must use remove or merge at least once.
Below are the operations you do to the above list of EXISTING RULES:
"""