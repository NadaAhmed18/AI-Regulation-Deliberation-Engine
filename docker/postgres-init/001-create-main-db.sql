-- Runs automatically on the Postgres container's FIRST boot only (the
-- official postgres image executes every .sql/.sh file under
-- /docker-entrypoint-initdb.d/, in filename order, but ONLY when the
-- data directory is empty -- it will NOT re-run on an existing volume).
--
-- Without this: POSTGRES_DB in docker/.env only creates the "langfuse"
-- database. The backend app's own DATABASE_URL (see backend/src/config.py)
-- points at a separate database named "main" by default -- which would
-- otherwise never get created, and the backend would fail to connect on
-- a fresh deploy with "database main does not exist".
--
-- This keeps the app's own simulation/discussion data in a logically
-- separate database from Langfuse's observability data, while still
-- sharing one Postgres server/container (and therefore one compute+
-- storage allocation) -- see docs/ for the tradeoffs of splitting this
-- into a fully separate Postgres instance later if "main" ever needs to
-- scale independently of Langfuse's traces.
CREATE DATABASE main;
GRANT ALL PRIVILEGES ON DATABASE main TO CURRENT_USER;
