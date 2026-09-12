# Research Assignment QA Skill

This skill provides comprehensive quality assurance for research assignments, evaluating content against questions, rubrics, and citation standards while providing actionable feedback.

## Core Functionality

### Assignment Assessment
- Analyze research assignments against provided questions or prompts  
- Evaluate assignments against custom rubrics (provided by user or institution)
- Score assignments on a standardized scale with detailed feedback
- Identify areas of improvement in content, structure, and argumentation

### Scoring and Improvement Suggestions
- Provide quantitative scores based on rubric criteria
- Offer qualitative feedback highlighting strengths and weaknesses  
- Suggest specific improvements for each identified area
- Include actionable recommendations with implementation guidance
- Provide an option to automatically apply suggested improvements (with user confirmation)

### Citation and Reference Checker  
- Verify all citations align with specified citation style (default: APA 7th edition)
- Check reference list formatting consistency
- Validate in-text citations match reference entries
- Identify missing or incorrect citations
- Suggest corrections with explanations

## Additional QA Checks Implemented

### Content Quality
- Logical Flow: Assess whether ideas progress logically and coherently
- Argument Strength: Evaluate the strength of arguments and evidence presented  
- Critical Thinking: Check for analysis, synthesis, and evaluation of sources
- Clarity and Precision: Identify areas where language could be clearer or more precise

### Structure and Organization
- Introduction and Thesis: Verify presence and quality of thesis statement
- Paragraph Development: Check paragraph unity, coherence, and transitions
- Section Organization: Ensure logical organization of sections and subsections
- Conclusion Effectiveness: Evaluate whether conclusions adequately summarize and synthesize

### Academic Standards
- Source Integration: Assess how well sources are integrated into the argument
- Avoidance of Plagiarism: Check for proper attribution and originality  
- Scholarly Tone: Ensure appropriate academic register and voice
- Evidence Sufficiency: Verify that claims are adequately supported

### Technical Requirements
- Format Compliance: Check adherence to required formatting standards (margins, font, spacing)  
- Table of Contents: Validate presence and accuracy if required
- Page Numbers: Ensure proper pagination where needed
- Figures and Tables: Verify correct labeling and referencing

## User Interaction Features

### Customization Options
- Ability to specify target audience (students, academics, industry professionals)
- Option to select quality standards (academic, professional, general audience)
- Support for custom rubrics provided by users or institutions  
- Flexible citation style selection (APA, MLA, Chicago, IEEE)

### Feedback Presentation
- Clear scoring breakdown with justification for each score
- Detailed improvement suggestions with specific examples
- Visual indicators for different severity levels of issues
- Implementation guidance that can be automatically applied

## Technical Implementation Considerations

### Integration Points
- API endpoints for rubric management
- Citation style validation engine  
- Document processing capabilities
- User preference storage and retrieval

### Scalability Requirements
- Support for various document formats (Word, PDF, LaTeX)
- Parallel processing for batch evaluation
- Cloud-based infrastructure for handling large volumes
- Version control for rubrics and citation rules

## Expected Outcomes

This skill provides:
1. Comprehensive assessment of research assignments
2. Detailed scoring with clear rationale 
3. Actionable improvement suggestions
4. Citation validation and correction capabilities
5. Flexible customization for different use cases
6. User-friendly interface for feedback review and implementation

## Usage Example

```bash
python -m passist.skills.research-assignment-qa.research_assignment_qa \
  --assignment /path/to/assignment.txt \
  --rubric /path/to/rubric.json \
  --style apa \
  --audience student
```

## Files Created

All temporary working files are written to the dedicated temp directory: `/home/praddesilva/ProjectTeams/personal-assistant/temp`