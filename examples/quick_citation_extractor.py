#!/usr/bin/env python3
"""
Live MCP Citation Extractor
A simple function to get citation info from MCP search results.
"""

import json
import re
from typing import List, Dict


def get_citations_from_mcp_results(mcp_results: List[str], show_details: bool = True) -> List[Dict]:
    """
    Extract and display citation information from MCP Qdrant search results.
    
    Args:
        mcp_results: The list of strings returned by mcp_qdrant_qdrant-find
        show_details: If True, print detailed citation information
        
    Returns:
        List of dictionaries containing citation information
    """
    citations = []
    
    # Skip the first item (query description)
    for i, entry in enumerate(mcp_results[1:], 1):
        if not (entry.startswith('<entry>') and entry.endswith('</entry>')):
            continue
            
        # Extract metadata
        metadata_match = re.search(r'<metadata>(.*?)</metadata>', entry, re.DOTALL)
        if not metadata_match:
            continue
            
        try:
            metadata = json.loads(metadata_match.group(1).strip())
        except json.JSONDecodeError:
            continue
        
        # Extract content
        content_match = re.search(r'<content>(.*?)</content>', entry, re.DOTALL)
        content = content_match.group(1).strip() if content_match else "No content"
        
        # Build citation info
        citation = {
            'number': i,
            'book': metadata.get("title", "Unknown Title"),
            'authors': metadata.get("authors", "Unknown Authors"),
            'year': str(metadata.get("year", "Unknown")),
            'chapter': metadata.get("chapter", "Unknown Chapter"),
            'page': str(metadata.get("page_number", "Unknown")),
            'publisher': metadata.get("publisher", "Unknown Publisher"),
            'content_preview': content[:150] + "..." if len(content) > 150 else content,
            'apa_citation': f"{metadata.get('authors', 'Unknown Authors')} ({metadata.get('year', 'Unknown')}). {metadata.get('title', 'Unknown Title')}. {metadata.get('publisher', 'Unknown Publisher')}. Page {metadata.get('page_number', 'Unknown')}."
        }
        
        citations.append(citation)
        
        if show_details:
            print(f"\n📖 {i}. {citation['book']}")
            print(f"   👤 {citation['authors']} ({citation['year']})")
            print(f"   📄 Page {citation['page']} | 📚 {citation['publisher']}")
            print(f"   💬 {citation['content_preview']}")
            print(f"   📝 Citation: {citation['apa_citation']}")
            print("-" * 80)
    
    return citations


def quick_citation_summary(mcp_results: List[str]) -> None:
    """Quick summary of just the book, author, year, and page info."""
    print("📚 QUICK CITATION REFERENCE")
    print("=" * 60)
    
    citations = get_citations_from_mcp_results(mcp_results, show_details=False)
    
    for citation in citations:
        print(f"{citation['number']}. {citation['authors']} ({citation['year']}) - {citation['book']}, p. {citation['page']}")
    
    print("=" * 60)


# Example usage function
def demo_with_search():
    """
    Example function showing how to use this with actual MCP search.
    Replace this with real MCP search results.
    """
    print("To use this with actual MCP search results:")
    print("1. Do your MCP search: results = mcp_qdrant_qdrant-find('your query')")
    print("2. Extract citations: citations = get_citations_from_mcp_results(results)")
    print("3. Or get quick summary: quick_citation_summary(results)")


if __name__ == "__main__":
    demo_with_search()