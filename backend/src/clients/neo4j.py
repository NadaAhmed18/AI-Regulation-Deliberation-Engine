import os
from neo4j import GraphDatabase
from src.config import VECTOR_DIMENSION
import logging

# Silence Neo4j info/notification logs in the console
logging.getLogger("neo4j").setLevel(logging.WARNING)

class Neo4jClient:
    _instance = None
    driver = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            user = os.environ.get("NEO4J_USERNAME", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "password123")
            cls._instance.driver = GraphDatabase.driver(uri, auth=(user, password))
        return cls._instance
    
    def close(self):
        if self.driver is not None:
            self.driver.close()
        
    def execute_query(self, query, parameters=None):
        """Executes a write/read query and returns the records."""
        if self.driver is None:
            raise RuntimeError("Database driver not initialized.")
            
        with self.driver.session() as session: # type: ignore
            result = session.run(query, parameters or {})
            return result.data()
        
    def setup_database(self):
        """Set up schema constraints for documents"""
        self.execute_query(
            "CREATE CONSTRAINT document_url_unique IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.document_url IS UNIQUE"
        )
        self.execute_query(
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
        )
        
    def setup_vector_index(self, index_name: str = "chunk_vector_index", dimension: int = VECTOR_DIMENSION): 
        """Creates the vector index on Chunk embedding property."""
        self.execute_query(
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.embedding) "
            "OPTIONS {"
            "  indexConfig: {"
            "    `vector.dimensions`: $dim,"
            "    `vector.similarity_function`: 'cosine'"
            "  }"
            "}",
            parameters={"dim": dimension}
        )
        return index_name