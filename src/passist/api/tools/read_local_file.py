"""
Tool for reading local files including Word, Excel, PowerPoint, and PDF documents.
This tool extracts text content from various document formats and returns it along with basic metadata.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
from pathlib import Path
from ..registry import ToolSpec

class ReadLocalFileArgs(BaseModel):
    """Arguments for readLocalFile tool"""
    path: str  # The path to the local file to read
    
class ReadLocalFileResult(BaseModel):
    """Result from readLocalFile tool"""
    text: str  # Extracted text content from the document
    meta: Dict[str, Any]  # Metadata about the document

def run_read_local_file(args: ReadLocalFileArgs) -> Dict[str, Any]:
    """
    Read a local file and extract its content.
    
    Args:
        args: ReadLocalFileArgs containing the file path
        
    Returns:
        Dictionary with extracted text and metadata
    """
    # Check if file exists
    if not os.path.exists(args.path):
        raise FileNotFoundError(f"File not found: {args.path}")
        
    # Get file extension
    file_extension = Path(args.path).suffix.lower()
    
    try:
        # Handle different file types
        if file_extension in ['.doc', '.docx']:
            return _read_word_file(args.path)
        elif file_extension in ['.xls', '.xlsx']:
            return _read_excel_file(args.path)
        elif file_extension in ['.ppt', '.pptx']:
            return _read_powerpoint_file(args.path)
        elif file_extension == '.pdf':
            return _read_pdf_file(args.path)
        elif file_extension in ['.txt', '.md']:
            return _read_text_file(args.path)
        else:
            # Try to read as text for unknown types
            return _read_text_file(args.path)
            
    except Exception as e:
        raise Exception(f"Error reading file {args.path}: {str(e)}")

# Tool specification - the very last line of this file
spec = ToolSpec(
    name="readLocalFile",
    description="Read a local .md/.txt/.docx/.pdf and return extracted text + basic metadata",
    side_effect=False,  # Read-only operation
    input_model=ReadLocalFileArgs,
    run=run_read_local_file
)
