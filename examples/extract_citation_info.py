#!/usr/bin/env python3
"""
Citation Information Extractor for MCP Qdrant Results
Extracts book, chapter, and page information from MCP search results.
"""

import json
import re
from typing import Dict, List, Optional


def extract_citation_from_metadata(metadata_dict: Dict) -> Dict[str, str]:
    """
    Extract citation information from metadata dictionary.
    
    Args:
        metadata_dict: Metadata dictionary from MCP result
        
    Returns:
        Dictionary with formatted citation information
    """
    citation = {
        "book": metadata_dict.get("title", "Unknown Title"),
        "authors": metadata_dict.get("authors", "Unknown Authors"),
        "year": str(metadata_dict.get("year", "Unknown Year")),
        "publisher": metadata_dict.get("publisher", "Unknown Publisher"),
        "chapter": metadata_dict.get("chapter", "Unknown Chapter"),
        "page": str(metadata_dict.get("page_number", "Unknown Page")),
        "source_file": metadata_dict.get("source_file", "Unknown Source")
    }
    
    return citation


def format_citation_apa(citation: Dict[str, str]) -> str:
    """
    Format citation in APA style.
    
    Args:
        citation: Citation dictionary from extract_citation_from_metadata
        
    Returns:
        APA formatted citation string
    """
    return f"{citation['authors']} ({citation['year']}). {citation['book']}. {citation['publisher']}. Chapter: {citation['chapter']}, Page: {citation['page']}"


def format_citation_chicago(citation: Dict[str, str]) -> str:
    """
    Format citation in Chicago style.
    
    Args:
        citation: Citation dictionary from extract_citation_from_metadata
        
    Returns:
        Chicago formatted citation string
    """
    return f"{citation['authors']}. {citation['book']}. {citation['publisher']}, {citation['year']}. Chapter: {citation['chapter']}, Page: {citation['page']}"


def parse_mcp_result_entry(entry_text: str) -> Optional[Dict]:
    """
    Parse a single MCP result entry to extract content and metadata.
    
    Args:
        entry_text: Raw entry text from MCP result
        
    Returns:
        Dictionary with content and parsed metadata, or None if parsing fails
    """
    # Extract content between <content> tags
    content_match = re.search(r'<content>(.*?)</content>', entry_text, re.DOTALL)
    if not content_match:
        return None
        
    content = content_match.group(1).strip()
    
    # Extract metadata between <metadata> tags
    metadata_match = re.search(r'<metadata>(.*?)</metadata>', entry_text, re.DOTALL)
    if not metadata_match:
        return None
        
    try:
        metadata_json = metadata_match.group(1).strip()
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return None
    
    citation = extract_citation_from_metadata(metadata)
    
    return {
        "content": content,
        "metadata": metadata,
        "citation": citation,
        "citation_apa": format_citation_apa(citation),
        "citation_chicago": format_citation_chicago(citation)
    }


def process_mcp_search_results(search_results: List[str]) -> List[Dict]:
    """
    Process complete MCP search results and extract citation info for all entries.
    
    Args:
        search_results: List of MCP search result strings
        
    Returns:
        List of processed entries with citation information
    """
    processed_entries = []
    
    # Skip the first item which is usually just the query description
    for entry_text in search_results[1:]:
        if entry_text.startswith('<entry>') and entry_text.endswith('</entry>'):
            parsed = parse_mcp_result_entry(entry_text)
            if parsed:
                processed_entries.append(parsed)
    
    return processed_entries


def print_citations_summary(processed_entries: List[Dict]) -> None:
    """
    Print a summary of all citations found in the search results.
    
    Args:
        processed_entries: List of processed entries from process_mcp_search_results
    """
    print("📚 Citation Summary")
    print("=" * 50)
    
    for i, entry in enumerate(processed_entries, 1):
        citation = entry["citation"]
        print(f"\n{i}. {citation['book']}")
        print(f"   Authors: {citation['authors']}")
        print(f"   Year: {citation['year']}")
        print(f"   Chapter: {citation['chapter']}")
        print(f"   Page: {citation['page']}")
        print(f"   Publisher: {citation['publisher']}")
        print(f"   APA: {entry['citation_apa']}")
        print("-" * 40)


if __name__ == "__main__":
    # Example usage with mock data
    example_results = [
        "Results for the query 'test query'",
        '<entry><content>Some content here</content><metadata>{"book": "Test Book", "authors": "Test Author", "year": 2023, "chapter": "Chapter 1", "page_number": 42, "publisher": "Test Publisher"}</metadata></entry>'
    ]
    
    processed = process_mcp_search_results(example_results)
    print_citations_summary(processed)