UNIFIED_RESEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "research_policy_evidence",
        "description": "Comprehensive research tool. Accepts multiple queries at once. Searches internal policy databases, queries the live web for missing context, and automatically ingests cited sources in a single execution.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of search queries or angles to investigate simultaneously (e.g. ['EU AI Act compute veto', 'NIST hardware tracking standards']).",
                },
                "document_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of exact document URLs to inspect directly.",
                },
            },
            "required": ["queries"],
        },
    },
}

# Keep stakeholder tools minimal and focused
ALL_TOOL_SCHEMAS = [
    UNIFIED_RESEARCH_TOOL_SCHEMA,
]