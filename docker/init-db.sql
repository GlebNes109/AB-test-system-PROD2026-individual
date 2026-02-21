-- Создаётся при первом старте postgres-контейнера (только если data-каталог пуст).
SELECT 'CREATE DATABASE metabase'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'metabase')
\gexec
