"""
Set-based filtering for organizing documents into logical groups.

Provides semantic matching to map queries to document sets.

Source: https://github.com/mahmoudimus/mcp-server-qdrant
Commit: 5af3f72f1afd1afa8dce39976cd29191ddb69887
Author: Mahmoud Rusty Abdelkader (@mahmoudimus)
License: Apache-2.0
"""

import json
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentSet:
    """Represents a set of documents."""

    slug: str
    description: str
    aliases: List[str]


class SetMatcher:
    """
    Matches queries to document sets using semantic matching.
    """

    def __init__(self, sets_config_path: Optional[str] = None):
        """
        Initialize the set matcher.
        :param sets_config_path: Path to sets configuration file
        """
        self.sets: Dict[str, DocumentSet] = {}
        self.load_sets(sets_config_path)

    def load_sets(self, config_path: Optional[str] = None):
        """
        Load document sets from configuration file.
        :param config_path: Path to configuration file
        """
        # Try to find config file
        if config_path:
            path = Path(config_path)
        else:
            # Look for default .qdrant_sets.json
            path = Path(".qdrant_sets.json")
            if not path.exists():
                logger.info("No sets configuration found. Set-based filtering disabled.")
                return

        if not path.exists():
            logger.warning(f"Sets configuration file not found: {path}")
            return

        try:
            with open(path, "r") as f:
                config = json.load(f)

            for set_config in config.get("sets", []):
                slug = set_config["slug"]
                description = set_config["description"]
                aliases = set_config.get("aliases", [])

                self.sets[slug] = DocumentSet(
                    slug=slug, description=description, aliases=aliases
                )

            logger.info(f"Loaded {len(self.sets)} document sets from {path}")

        except Exception as e:
            logger.error(f"Failed to load sets configuration: {e}")

    def match_set(self, query: str) -> Optional[str]:
        """
        Match a query to a document set slug using semantic matching.
        :param query: Natural language query
        :return: Matched set slug or None
        """
        if not self.sets:
            return None

        query_lower = query.lower()
        best_match = None
        best_score = 0.0

        for slug, doc_set in self.sets.items():
            # Try exact slug match first
            if slug.lower() == query_lower:
                return slug

            # Check aliases
            for alias in doc_set.aliases:
                if alias.lower() == query_lower:
                    return slug

            # Check if query is in description
            if query_lower in doc_set.description.lower():
                score = len(query_lower) / len(doc_set.description)
                if score > best_score:
                    best_score = score
                    best_match = slug

            # Use fuzzy matching on description
            similarity = SequenceMatcher(
                None, query_lower, doc_set.description.lower()
            ).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = slug

        # Return match if score is above threshold
        if best_score > 0.3:  # 30% similarity threshold
            logger.info(f"Matched query '{query}' to set '{best_match}' (score: {best_score:.2f})")
            return best_match

        logger.debug(f"No good match found for query '{query}'")
        return None

    def get_available_sets(self) -> List[str]:
        """
        Get list of available set slugs.
        :return: List of set slugs
        """
        return list(self.sets.keys())
