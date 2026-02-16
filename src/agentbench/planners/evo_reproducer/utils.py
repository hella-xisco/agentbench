import re
from typing import Dict, List, Tuple

def extract_rule_blocks(text: str) -> Tuple[str, str, str]:
    """
    Returns:
      all_repo_block: the full <all_repo_rules>...</all_repo_rules> substring (or "")
      repo_block:     the full <{repo}_rules>...</{repo}_rules> substring (or "")
      repo_name:      the repo name between the tag and '_rules' (or "")
    """
    # 1) All-repo block
    m_all = re.search(
        r"<all_repo_rules>\s*.*?\s*</all_repo_rules>",
        text,
        flags=re.DOTALL,
    )
    all_repo_block = m_all.group(0) if m_all else ""

    # 2) Specific repo block — exclude "all_repo_rules"
    #    Allow letters, digits, underscore, dot, dash, and optional braces in the name.
    m_repo = re.search(
        r"<(?!all_repo_rules)([A-Za-z0-9_.\-\{\}]+)_rules>\s*.*?\s*</\1_rules>",
        text,
        flags=re.DOTALL,
    )
    repo_block = m_repo.group(0) if m_repo else ""
    repo_name = m_repo.group(1) if m_repo else ""

    # Normalize {repo} → repo if braces are used literally
    if repo_name.startswith("{") and repo_name.endswith("}"):
        repo_name = repo_name[1:-1].strip()

    return all_repo_block, repo_block, repo_name


def parse_rules(llm_text):
    ans = {}

    # This was the old parsing logic before we added the tags
    # It was unreliabled so I replaced it with the new tag-based parsing above
    # llm_text.strip("\n")
    # parts = llm_text.split("\n\n", 1)
    # if len(parts) < 2:
    #     return ans
    # gen_exp, spe_exp = parts[0], parts[1]
    # repo = spe_exp.split(":")[0].strip().split(" ")[1]

    llm_text.strip("\n")
    all_repo_block, repo_block, repo = extract_rule_blocks(llm_text)
    gen_exp = all_repo_block
    spe_exp = repo_block

    pattern = r"((?:REMOVE|EDIT|AGREE) \d+|MERGE \d+ \d+|ADD|ADD \d): (?:[a-zA-Z\s\d]+: |)(.*)"
    gen_matches = re.findall(pattern, gen_exp)
    res = []
    banned_words = ["ADD", "AGREE", "EDIT"]
    for operation, text in gen_matches:
        text = text.strip()
        if (
            text != ""
            and not any([w in text for w in banned_words])
            and text.endswith(".")
        ):
            # if text is not empty
            # if text doesn't contain banned words (avoid weird formatting cases from llm)
            # if text ends with a period (avoid cut off sentences from llm)
            if "ADD" in operation:
                res.append(("ADD", text))
            else:
                res.append((operation.strip(), text))

    ans["general"] = res

    exp_matches = re.findall(pattern, spe_exp)
    res = []
    banned_words = ["ADD", "AGREE", "EDIT"]
    for operation, text in exp_matches:
        text = text.strip()
        if (
            text != ""
            and not any([w in text for w in banned_words])
            and text.endswith(".")
        ):
            # if text is not empty
            # if text doesn't contain banned words (avoid weird formatting cases from llm)
            # if text ends with a period (avoid cut off sentences from llm)
            if "ADD" in operation:
                res.append(("ADD", text))
            else:
                res.append((operation.strip(), text))
    ans[repo] = res

    return ans


def parse_rules_merge(llm_text):
    ans = {}
    # logger.debug(llm_text)
    llm_text.strip("\n")
    gen_exp = llm_text
    pattern = r"((?:REMOVE|EDIT|AGREE) \d+|MERGE \d+ \d+|ADD|ADD \d): (?:[a-zA-Z\s\d]+: |)(.*)"
    gen_matches = re.findall(pattern, gen_exp)
    res = []
    banned_words = ["ADD", "AGREE", "EDIT"]
    for operation, text in gen_matches:
        text = text.strip()
        if (
            text != ""
            and not any([w in text for w in banned_words])
            and text.endswith(".")
        ):
            # if text is not empty
            # if text doesn't contain banned words (avoid weird formatting cases from llm)
            # if text ends with a period (avoid cut off sentences from llm)
            if "ADD" in operation:
                res.append(("ADD", text))
            else:
                res.append((operation.strip(), text))

    ans["general"] = res
    return ans


def retrieve_rule_index(rules, operation):
    operation_rule_text = operation[1]
    for i in range(len(rules)):
        if rules[i][0] in operation_rule_text:
            return i


def is_existing_rule(rules, operation_rule_text):
    for i in range(len(rules)):
        if rules[i][0] in operation_rule_text:
            return True
    return False


def update_rules(
    rules: Dict[str, List[Tuple[str, int]]],
    operations_map: Dict[str, List[Tuple[str, str]]],
    list_full: bool = False,
) -> List[Tuple[str, int]]:
    # remove problematic operations
    for key in operations_map.keys():
        if key not in rules:
            rules[key] = []
        operations = operations_map[key]

        delete_indices = []
        for i in range(len(operations)):
            operation, operation_rule_text = operations[i]
            operation_type = operation.split(" ")[0]
            if operation_type == "MERGE":
                rule_num1 = int(operation.split(" ")[1])
                rule_num2 = int(operation.split(" ")[2])
                if rule_num1 == rule_num2:
                    delete_indices.append(i)

            else:
                rule_num = int(operation.split(" ")[1]) if " " in operation else None

            if operation_type == "ADD":
                if is_existing_rule(
                    rules[key], operation_rule_text
                ):  # if new rule_text is an existing rule ('in')
                    delete_indices.append(i)
            else:
                if operation_type == "EDIT":
                    if is_existing_rule(
                        rules[key], operation_rule_text
                    ):  # if rule is matching ('in') existing rule, change it to AGREE
                        rule_num = retrieve_rule_index(
                            rules[key], (operation, operation_rule_text)
                        )
                        operations[i] = (
                            f"AGREE {rule_num + 1}",
                            rules[key][rule_num][0],
                        )
                    elif (rule_num is None) or (
                        rule_num > len(rules[key])
                    ):  # if rule doesn't exist, remove
                        delete_indices.append(i)

                elif operation_type == "REMOVE" or operation_type == "AGREE":
                    if not is_existing_rule(
                        rules[key], operation_rule_text
                    ):  # if new operation_rule_text is not an existing rule
                        delete_indices.append(i)

                elif operation_type == "MERGE":
                    if (
                        (rule_num1 is None)
                        or (rule_num2 is None)
                        or (rule_num1 > len(rules[key]) or rule_num2 > len(rules[key]))
                    ):  # if rule doesn't exist, remove
                        delete_indices.append(i)

        operations = [
            operations[i] for i in range(len(operations)) if i not in delete_indices
        ]  # remove problematic operations

        for op in ["REMOVE", "MERGE", "AGREE", "EDIT", "ADD"]:  # Order is important
            for i in range(len(operations)):
                operation, operation_rule_text = operations[i]
                operation_type = operation.split(" ")[0]
                if operation_type != op:
                    continue

                if operation_type == "REMOVE":  # remove rule: -1
                    rule_index = retrieve_rule_index(
                        rules[key], (operation, operation_rule_text)
                    )  # if rule_num doesn't match but text does
                    remove_strength = 3
                    rules[key][rule_index] = [
                        rules[key][rule_index][0],
                        rules[key][rule_index][1] - remove_strength,
                    ]  # -1 (-3 if list full) to the counter
                elif operation_type == "MERGE":
                    rule_index1 = int(operation.split(" ")[1]) - 1
                    rule_index2 = int(operation.split(" ")[2]) - 1
                    rules[key][rule_index1] = [
                        operation_rule_text,
                        max(rules[key][rule_index1][1], rules[key][rule_index2][1]),
                    ]
                    rules[key][rule_index2] = [rules[key][rule_index2][0], 0]
                elif operation_type == "AGREE":  # agree with rule: +1
                    rule_index = retrieve_rule_index(
                        rules[key], (operation, operation_rule_text)
                    )  # if rule_num doesn't match but text does
                    rules[key][rule_index] = [
                        rules[key][rule_index][0],
                        rules[key][rule_index][1] + 1,
                    ]  # +1 to the counter
                elif (
                    operation_type == "EDIT"
                ):  # edit the rule: +1 // NEED TO BE AFTER REMOVE AND AGREE
                    rule_index = int(operation.split(" ")[1]) - 1
                    rules[key][rule_index] = [
                        operation_rule_text,
                        rules[key][rule_index][1] + 1,
                    ]  # +1 to the counter
                elif operation_type == "ADD":  # add new rule: +2
                    rules[key].append([operation_rule_text, 2])
        before_cleanup = len(rules[key])
        rules[key] = [
            rules[key][i] for i in range(len(rules[key])) if rules[key][i][1] > 0
        ]  # remove rules when counter reach 0
        rules[key].sort(key=lambda x: x[1], reverse=True)

    return rules
