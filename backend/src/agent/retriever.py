# python -m src.agent.retriever
from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from src.config import EMBEDDING_MODEL

class KnowledgeRetrieverTool:
    """
    A unified retrieval interface designed to be passed to LLMs as a tool.
    It handles vector embedding and Neo4j graph traversal automatically.
    """
    def __init__(self):
        self.db = Neo4jClient()
        self.embedder = Embedder(model_name=EMBEDDING_MODEL)
        self.index_name = "chunk_vector_index"

    def search_ai_policy(self, query: str, top_k: int = 3) -> str:
        """
        TOOL NAME: search_ai_policy
        DESCRIPTION: Use this tool to search the knowledge database for factual information 
        regarding AI regulations, laws, democratic values, and stakeholder opinions.
        
        Args:
            query (str): The search question or topic (e.g., "What are the rules for High-Risk AI?").
            top_k (int): Number of sources to retrieve. Defaults to 3.
            
        Returns:
            str: A formatted string containing the retrieved policy text and source URLs, ready for the LLM to read.
        """
        print(f"\n[Agent Tool] 🔍 Searching knowledge base for: '{query}'")
        
        # 1. Convert LLM's text query into a vector
        query_embedding = self.embedder.embed([query], is_query=True)[0].tolist()

        # 2. Query Neo4j
        cypher_query = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
        YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        RETURN 
            chunk.text AS text, 
            doc.document_url AS source_url, 
            doc.domain AS domain,
            score AS similarity_score
        ORDER BY score DESC
        """
        
        parameters = {
            "index_name": self.index_name,
            "top_k": top_k,
            "query_embedding": query_embedding
        }

        results = self.db.execute_query(cypher_query, parameters)
        
        # 3. Format output specifically for an LLM to read easily
        if not results:
            return "No relevant information found in the database for this query."
            
        llm_formatted_response = "Here is the retrieved context from the database:\n\n"
        for i, r in enumerate(results, 1):
            llm_formatted_response += f"--- SOURCE {i} ---\n"
            llm_formatted_response += f"Domain: {r['domain']}\n"
            llm_formatted_response += f"URL: {r['source_url']}\n"
            llm_formatted_response += f"Relevance Score: {round(r['similarity_score'], 4)}\n"
            llm_formatted_response += f"Content:\n{r['text']}\n\n"
            
        return llm_formatted_response

# ==========================================
# Testing the Tool wrapper
# ==========================================
if __name__ == "__main__":
    tool = KnowledgeRetrieverTool()
    
    # Simulate an LLM calling the tool
    agent_query = "What is the EU AI Act and what does it say about High-Risk AI?"
    response = tool.search_ai_policy(query=agent_query, top_k=2)
    
    print("Output sent to LLM:\n")
    print(response)