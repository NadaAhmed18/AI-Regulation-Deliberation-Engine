from fastapi import Request
from src.clients.postgres import PostgresClient
from src.clients.neo4j import Neo4jClient

def get_pg_client(request: Request) -> PostgresClient:
    """Returns the singleton pooled PostgresClient instance from app.state."""
    return request.app.pg_client

def get_neo4j_client(request: Request) -> Neo4jClient:
    """Returns the singleton Neo4jClient driver instance from app.state."""
    return request.app.neo4j_client