RETRIEVER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_ai_policy",
        "description": "Search the internal knowledge base for AI policy regulations using a semantic query, a direct document URL, or both.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search question or keywords (e.g., 'High-Risk AI obligations'). Optional if document_url is provided.",
                },
                "document_url": {
                    "type": "string",
                    "description": "Optional exact URL of a specific document to inspect or restrict search to.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of document chunks to retrieve (default: 3).",
                },
            },
        },
    },
}

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the live internet for recent news, policy updates, and URLs relevant to the topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g., 'US Executive Order AI safety standards 2026').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to retrieve (default: 3, max: 5).",
                },
            },
            "required": ["query"],
        },
    },
}

WEB_LEARNER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "learn_and_ingest_url",
        "description": "Scrapes a URL, extracts its text and related links, and permanently saves it into the Neo4j knowledge database for future retrieval. Returns a preview of the content.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The HTTP/HTTPS URL of the web page to scrape and learn.",
                },
            },
            "required": ["url"],
        },
    },
}

ALL_TOOL_SCHEMAS = [
    RETRIEVER_TOOL_SCHEMA,
    WEB_SEARCH_TOOL_SCHEMA,
    WEB_LEARNER_TOOL_SCHEMA,
]