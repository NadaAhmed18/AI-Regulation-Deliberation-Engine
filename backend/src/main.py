import logging
from fastapi import FastAPI

from src.clients.postgres import PostgresClient
from src.clients.neo4j import Neo4jClient
from src.routes.simulation_router import simulation_router
from src.routes.base_router import base_router

logger = logging.getLogger("uvicorn")

def lifespan(app: FastAPI):

    logger.info("Initializing database clients on startup...")
    
    pg_client = PostgresClient()
    
    neo4j_client = Neo4jClient()

    app.pg_client = pg_client
    app.neo4j_client = neo4j_client
    
    logger.info("All database clients initialized and ready.")
    yield

    # Teardown logic
    logger.info("Application shutting down: Closing database pools...")
    app.pg_client=None
    neo4j_client.close()
    logger.info("All database connections gracefully closed.")


app = FastAPI(

)

app.include_router(base_router)
app.include_router(simulation_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)