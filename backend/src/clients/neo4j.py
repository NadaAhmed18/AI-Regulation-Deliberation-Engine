import os
from neo4j import GraphDatabase
from config import VECTOR_DIMENSION

class Neo4jClient:
    client = None
    
    def __new__(cls):
        if cls.client is None:
            cls.client = super().__new__(cls)
        return cls.client
    
    def __init__(self):
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USERNAME", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password123")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()
        
    def execute_query(self, query, parameters=None):
        """Executes a write/read query and returns the records."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return result.data()
        
    def setup_database(self):
        """Set up schema constraints for documents"""
        # Ensure document_url is unique
        self.execute_query(
            "CREATE CONSTRAINT document_url_unique IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.document_url IS UNIQUE"
        )
        
    def setup_vector_index(self, index_name: str = "document_voyage_vector_index", dimension: int = VECTOR_DIMENSION): 
        """Creates the vector index on Document embedding property for Voyage AI."""
        self.execute_query(f"DROP INDEX {index_name} IF EXISTS")
        self.execute_query(
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            "FOR (d:Document) ON (d.embedding) "
            "OPTIONS {"
            "  indexConfig: {"
            "    `vector.dimensions`: $dim,"
            "    `vector.similarity_function`: 'cosine'"
            "  }"
            "}",
            parameters={"dim": dimension}
        )
        return index_name