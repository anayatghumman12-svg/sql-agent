-- The agent connects with this role; it can only read data.
CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';
GRANT CONNECT ON DATABASE shop TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;