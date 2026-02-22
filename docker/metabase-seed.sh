#!/bin/sh
set -e

SEED="/docker-entrypoint-initdb.d/metabase_seed.sql"
[ ! -f "$SEED" ] && echo "metabase_seed.sql not found, skipping" && exit 0

echo "Applying metabase seed..."
sed '/^\\restrict/d' "$SEED" | psql -U "$POSTGRES_USER" -d metabase
echo "Metabase seed applied."
