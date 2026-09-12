# Research AI Skill

This skill performs intelligent research on specified topics and generates output in multiple formats with proper APA citations.

## Overview

The Research AI skill enables users to conduct research on specific topics using different levels of academic rigor (academic, professional, or general) and output the results in various document formats including PowerPoint presentations, Word documents, PDFs, Markdown files, and Excel spreadsheets.

## Features

- **Multi-level Research**: Choose between academic, professional, or general research approaches
- **APA Citations**: All sources are properly formatted with APA-style citations  
- **Multiple Output Formats**: Generate results in PPTX, DOCX, PDF, MD, or XLSX formats
- **Smart Source Selection**: Automatically selects appropriate sources based on research level

## Usage

The skill can be invoked through the `researchAI` tool with the following arguments:

```
{
  "topic": "Artificial Intelligence in Healthcare",
  "level": "academic",
  "format": "md"
}
```

## Research Levels

- **Academic**: Scholarly articles, peer-reviewed research, academic databases
- **Professional**: Industry reports, expert opinions, professional resources  
- **General**: News sources, public information, general knowledge

## Output Formats

- **PPTX** - PowerPoint presentation with slides
- **DOCX** - Microsoft Word document  
- **PDF** - Printable PDF document
- **MD** - Markdown formatted text
- **XLSX** - Excel spreadsheet for data tables

## Dependencies

This skill requires the following extra packages:
- python-docx (for DOCX generation)
- python-pptx (for PPTX generation) 
- openpyxl (for XLSX generation)
- markdown (for MD formatting)

## Implementation Notes

The implementation handles citation formatting in APA style and includes:
- Proper in-text citations
- Reference lists with complete bibliographic information
- Automatic source type detection and formatting
- Consistent formatting across all output types

## File Structure

```
research-ai/
├── __init__.py          # Main skill implementation
├── setup.py            # Package configuration  
├── README.md           # This file
└── references/
    └── research-template.md  # Research document template
```

## Example Output

When searching for "Climate Change Mitigation", the skill produces a formatted report including:
- Introduction to the topic
- Findings based on chosen research level
- APA-formatted citations and references  
- Conclusion with implications

All research sources are properly cited using APA guidelines.