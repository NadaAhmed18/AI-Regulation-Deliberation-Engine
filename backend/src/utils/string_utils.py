"""
String Utilities

Provides common string manipulation and sanitization functions used 
across the DocuBot pipeline to ensure safe naming conventions for databases.
"""

import re

def get_safe_model_name(model_name: str) -> str:
    """
    Sanitizes a model name to be safely used as database indexes, 
    properties, or file paths. It forces lowercase and replaces any 
    non-alphanumeric character with an underscore.

    Examples:
        - "voyage-code-3" -> "voyage_code_3"
        - "Qwen/Qwen3-0.6B" -> "qwen_qwen3_0_6b"
        - "amazon.titan-embed-text-v2:0" -> "amazon_titan_embed_text_v2_0"

    Args:
        model_name (str): The raw model name from configuration.

    Returns:
        str: A safe, alphanumeric-only (plus underscores) string.
    """
    if not model_name:
        return "default_model"
        
    return re.sub(r'[^a-zA-Z0-9]', '_', model_name.lower())


def get_neo4j_index_and_property_names(model_name: str) -> tuple[str, str]:
    """
    Generates consistent, safe names for Neo4j Vector Indexes and Chunk properties.
    
    Args:
        model_name (str): The raw embedding model name.
        
    Returns:
        tuple[str, str]: (index_name, property_name)
        Example: ("idx_voyage_code_3", "emb_voyage_code_3")
    """
    safe_name = get_safe_model_name(model_name)
    return f"idx_{safe_name}", f"emb_{safe_name}"