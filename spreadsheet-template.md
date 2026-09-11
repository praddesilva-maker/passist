# Personal Assistant Spreadsheet Template

This template is designed to work with the passist personal assistant framework. It helps organize tasks, goals, and information that can be processed by the system's skills.

## Core Task Tracking

| ID | Goal Description | Status | Priority | Skill Match | Trigger | Inputs Needed | Expected Outcome | Notes |
|----|------------------|--------|----------|-------------|---------|---------------|------------------|-------|
| T001 | [Describe your goal here] | [Not Started/In Progress/Completed/On Hold] | [High/Medium/Low] | [Skill name if matched] | [Trigger text] | [List required inputs] | [Expected result] | [Additional notes] |

## Skill Usage Matrix

| Skill Name | Description | When to Use | Trigger | Inputs Required | Output Expected |
|------------|-------------|-------------|---------|-----------------|-----------------|
| use-capability | Route user's stated goal to the right existing tool or skill and run it | When you have a clear goal | "use passist — [your goal]" | Goal description | Matching capability information, inputs required |
| skill-reviewer | Review one skill to deliver an expert critique for distribution-readiness | When evaluating skill quality | "start skill review" | Skill name or description | Expert critique and findings |
| skill-hygiene-check | Audit fleet for conformance and return PASS/FAIL/N-A table | When checking system health | "start skill hygiene check" | None | Compliance status report |

## Project Planning

### Short-term Goals (Next 7 days)

| Goal | Skill Needed | Status | Deadline | Resources |
|------|--------------|--------|----------|-----------|
| [Goal description] | [Skill name] | [Not Started/In Progress/Completed] | [Date] | [Required resources] |

### Long-term Objectives (Next 30 days)

| Objective | Skill Match | Priority | Status | Estimated Completion |
|-----------|-------------|----------|--------|---------------------|
| [Objective description] | [Skill name] | [High/Medium/Low] | [Not Started/In Progress/Completed] | [Date] |

## Knowledge Management

### Information Sources

| Source Type | Source Name | Category | Last Updated | Status |
|-------------|-------------|----------|--------------|--------|
| Documentation | [Title] | [Category] | [Date] | [Status] |
| Web Resource | [URL] | [Category] | [Date] | [Status] |
| Personal Note | [Title] | [Category] | [Date] | [Status] |

### References

| Reference ID | Related Goal | Source Type | Description | Status |
|--------------|--------------|-------------|-------------|--------|
| REF001 | [Goal ID] | [Document/Web/Note] | [Brief description] | [Pending/Complete/Archived] |

## System Integration

### Tool Usage

| Tool Name | Use Case | Input Parameters | Expected Output | Status |
|-----------|----------|------------------|-----------------|--------|
| getThing | Read a thing from Personal Assist API by ID | `id` | Thing data | [Available/Used/Not Used] |
| updateThing | Update a thing in Personal Assist API by ID | `id`, `fields` | Updated thing data | [Available/Used/Not Used] |

### Capability Mapping

| Capability | Skill | Input Requirements | Tool Required | Estimated Time |
|------------|-------|-------------------|---------------|----------------|
| [Capability description] | [Matching skill] | [Required inputs] | [Tools needed] | [Time estimate] |

## Usage Recommendations

1. **Goal Definition**: Clearly define your goals using plain English for use-capability skill
2. **Skill Matching**: Refer to the Skills section when determining which skills to use
3. **Status Tracking**: Update statuses regularly to monitor progress
4. **Input Preparation**: List required inputs upfront to minimize back-and-forth

## Example Usage

To use this template with passist:

1. Describe your goal clearly in the "Goal Description" column
2. Let system match it to an appropriate skill using "use-capability"
3. Provide any necessary input parameters
4. Track your progress through the status columns