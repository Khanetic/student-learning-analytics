-- ===========================================================================
-- 00_databases.sql — bootstrap databases (runs once on first Postgres init)
-- ===========================================================================
-- The default database (POSTGRES_DB=sla) holds the application star schema.
-- Airflow needs its own metadata database; create it here so a single Postgres
-- container serves both. This script runs against the default `sla` database.
-- ===========================================================================

SELECT 'CREATE DATABASE airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
