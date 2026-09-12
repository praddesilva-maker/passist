# `research-ai`

An intelligent research skill that can perform research on various topics and deliver results in multiple output formats with APA citations.

## Intent

This skill performs comprehensive research on requested topics and delivers results in multiple document formats (PowerPoint, Word, PDF, Markdown, Excel) with proper APA citations. It allows users to select the research level (Academic, Professional, General) to determine source types and depth of investigation.

## Input Contract

- **Research Topic** — A string describing the topic to research
- **Research Level** — One of: "academic", "professional", or "general"
- **Output Format** — One of: "pptx", "docx", "pdf", "md", or "xlsx"

## Mode: Interactive (`interactive`)

1. Prompts user for research topic
2. Asks for research level (Academic, Professional, General)
3. Asks for desired output format (PowerPoint, Word, PDF, Markdown, Excel)
4. Conducts research based on selected parameters
5. Generates document with results and APA citations
6. Returns the completed file

## Mode: Single Command (`single-run`)

1. Takes research topic, level, and output format as arguments
2. Performs same research process as interactive mode
3. Returns completed document in specified format

### Arguments

- `topic` — String describing the research topic
- `level` — Research level ("academic", "professional", or "general") 
- `format` — Output format ("pptx", "docx", "pdf", "md", or "xlsx")

## Guardrails

- **Never fabricate** → use "To be confirmed" for unknowns  
- **Dry-run/plan default** — Default mode is planning, requires explicit confirmation to proceed with actual research
- **Explicit approval gate** before any file writes
- **Upsert, never duplicate** — Extend existing capabilities vs re-create them
- **Write-scope limited to research outputs only**
- **APA citation compliance** — All sources must be properly cited in APA format

## Grounding Sources

- Uses different search strategies based on research level:
  - Academic: Peer-reviewed journals, scholarly articles, academic databases
  - Professional: Industry publications, expert opinions, professional resources  
  - General: News sources, public information, general knowledge bases
- Generates documents in specified formats with proper APA citations

## Acceptance Criteria

1. Document generation completes successfully
2. Content is relevant to the research topic
3. Sources are appropriate for selected research level
4. All citations follow APA format correctly
5. Document maintains formatting integrity per output format
6. Generated files are properly structured and readable

## Implementation

### Interactive Mode Actions

1. Read search parameters from user (topic, level, format)
2. Validate inputs 
3. Determine appropriate sources based on research level
4. Execute search using selected source strategy
5. Compile findings into research document
6. Add APA citations to the document
7. Format document according to requested output format
8. Present completed document to user

### Single Run Mode Actions

1. Parse arguments for topic, level, and format  
2. Validate each argument
3. Proceed with same search and formatting process as interactive mode
4. Return completed file

## Run Receipt

```json
{
  "category": "research",
  "primary_volume": "number of pages in research document",
  "secondary_volume": "number of sources cited",
  "description": "research-ai skill performed research and generated a document in specified format"
}
```

## References

- `references/research-ai-template.md` – Research template used for generating outputs