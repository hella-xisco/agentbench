def extract_plan_from_patch(model_patch: str):
    """Extract the AGENTS.md content from a model_patch diff."""
    # Look for the AGENTS.md content in the diff
    # Or PROPOSED_CHANGES.md or CLAUDE.md or GEMINI.md depending on the planner
    # The pattern is: +content after +++ b/AGENTS.md
    lines = model_patch.split('\n')
    
    in_proposed_changes = False
    plan_lines = []
    
    for line in lines:
        # Start capturing when we see the PROPOSED_CHANGES.md file
        if line.startswith('+++ b/PROPOSED_CHANGES.md') or line.startswith('+++ b/AGENTS.md') or line.startswith('+++ b/CLAUDE.md') or line.startswith('+++ b/GEMINI.md'):
            in_proposed_changes = True
            continue
            
        # Stop capturing when we hit another file (starts with diff --git or +++)
        if in_proposed_changes and (line.startswith('diff --git') or 
                                  (line.startswith('+++') and ('PROPOSED_CHANGES.md' not in line and 'AGENTS.md' not in line and 'CLAUDE.md' not in line and 'GEMINI.md' not in line))):
            break
            
        # Capture content lines (those starting with +)
        if in_proposed_changes and line.startswith('+'):
            # Remove the leading + and add to plan
            plan_lines.append(line[1:])
    
    return '\n'.join(plan_lines).strip()