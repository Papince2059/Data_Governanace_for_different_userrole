-- =================================================================
-- PostgreSQL initialization script
-- =================================================================

-- Create openfga_db if it does not exist
SELECT 'CREATE DATABASE openfga_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'openfga_db')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE governance_db TO governance_user;
GRANT ALL PRIVILEGES ON DATABASE openfga_db TO governance_user;

-- Connect to governance_db and enable extensions
\connect governance_db;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Connect to openfga_db and enable extensions
\connect openfga_db;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
