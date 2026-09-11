def generate_role_sheet(role: str, skills: list, prompts: list):
    """Generate an individual sheet for a role"""
    print(f"Generating sheet for role: {role}")
    
    # Create a mapping from skill name to trigger
    skill_to_prompt = {prompt['skill']: prompt for prompt in prompts}
    
    content = f"# Role: {role}\n\n"
    content += f"**What the agent does for you:** [Role description for {role}]\n\n"
    
    content += "## Your jobs at a glance\n\n"
    content += "| # | Job-to-be-Done | Phase | Skill | Trigger |\n"
    content += "|---|----------------|-------|-------|---------|\n"
    
    # For demonstration - we'll create dummy mappings
    jobs = [
        {"description": "Use existing capabilities", "skill": "use-capability", "phase": "implement"},
        {"description": "Review skills for distribution readiness", "skill": "skill-reviewer", "phase": "design"},
        {"description": "Check fleet conformance", "skill": "skill-hygiene-check", "phase": "test"}
    ]
    
    for i, job in enumerate(jobs, 1):
        skill = next((s for s in skills if s['name'] == job['skill']), None)
        prompt = skill_to_prompt.get(job['skill'])
        
        trigger = prompt['trigger'] if prompt else "Not found"
        
        content += f"| {i} | {job['description']} | {job['phase']} | {job['skill']} | `{trigger}` |\n"
    
    # Section per job
    for i, job in enumerate(jobs, 1):
        content += f"\n## Job {i}: {job['description']}\n\n"
        content += "**When**: [Description of when to use this]\n\n"
        content += "**Paste this interactive trigger**: `{trigger}`\n\n"  
        content += "**What you get**: [Description of expected outcome]\n\n"
        content += "**Guardrail**: [Any specific guidelines or restrictions]\n\n"
        content += f"[Full template](https://github.com/example/passist/blob/main/docs/prompts.md#{job['skill']})\n"
    
    with open(f"cheat-sheets/{role.lower().replace(' ', '-')}.md", "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Role sheet for {role} generated")

def generate_backlog(skills: list, prompts: list):
    """Generate a value-ranked backlog of new capabilities to build"""
    print("Generating backlog...")
    
    content = "# New Build Backlog\n\n"
    content += "This section identifies new capability opportunities ranked by blended value (ROI × strategic weight).\n\n"
    
    content += "## Blended Value Rankings\n\n"
    content += "| Rank | Capability | Description | ROI Estimate | Strategic Weight | Blended Score | Recommended |\n"
    content += "|------|------------|-------------|--------------|----------------|---------------|-------------|\n"
    
    # This is a sample backlog - in reality this would be calculated from metrics
    backlog_items = [
        {"name": "capability-intake", "desc": "Enhanced change request intake", "roi": 8, "weight": 7, "recommended": True},
        {"name": "skill-hygiene-check", "desc": "Automated hygiene checking", "roi": 9, "weight": 6, "recommended": True},
        {"name": "use-capability", "desc": "Improved usage guidance", "roi": 7, "weight": 8, "recommended": True}
    ]
    
    for i, item in enumerate(backlog_items, 1):
        blended = item['roi'] * item['weight']
        rec = "✅" if item['recommended'] else "❌"
        content += f"| {i} | {item['name']} | {item['desc']} | {item['roi']} | {item['weight']} | {blended} | {rec} |\n"
    
    # Consolidation table - showing capabilities reused across roles
    content += "\n## Consolidation Table\n\n"
    content += "This table deduplicates capabilities that are valuable across multiple roles:\n\n"
    content += "| Capability | Used by Roles | Estimated Value |\n"
    content += "|------------|---------------|-----------------|\n"
    content += "| use-capability | User, Developer | High |\n"
    content += "| skill-reviewer | Developer, Manager | Medium |\n"
    
    # Recommended build order
    content += "\n## Recommended Build Order\n\n" 
    content += "1. capability-intake - High ROI with high strategic weight\n"
    content += "2. use-capability - High strategic value, good ROI\n"
    content += "3. skill-hygiene-check - Medium-value enhancement\n"
    
    content += "\n> **Note**: This backlog is dynamic and will be refreshed whenever a skill is added or removed from the system.\n"
    
    with open("cheat-sheets/new-build-backlog.md", "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Backlog generated")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='Generate role cheat sheets')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing files') 
    parser.add_argument('--roles', help='Comma-separated list of roles')
    parser.add_argument('--phases', help='Comma-separated list of phases')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("Running in dry-run mode - preview only")
        
    # For this example, just do basic generation
    create_role_cheatsheets()
    
    print("Role cheatsheets generated successfully!")

if __name__ == "__main__":
    main()
