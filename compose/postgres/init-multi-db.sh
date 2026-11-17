#!/usr/bin/env bash
# Central Intelligence — Multi-Tenant PostgreSQL Logical Database Initializer
# Consolidates multiple PostgreSQL services into a single PostgreSQL container (Lite & Standard profiles).
set -e
set -u

function create_db_and_user() {
  local db_name="$1"
  local db_user="${2:-$db_name}"
  local db_password="${3:-$db_name}"

  echo "[init-multi-db] Initializing database '$db_name' for user '$db_user'..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$db_user') THEN
        CREATE ROLE $db_user WITH LOGIN PASSWORD '$db_password';
      END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE $db_name OWNER $db_user'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db_name')\gexec

    GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;
EOSQL
  echo "[init-multi-db] Database '$db_name' initialized successfully."
}

# Read multiple databases from POSTGRES_MULTIPLE_DATABASES environment variable
# Format: "db1:user1:pass1,db2:user2:pass2" or comma-separated names "openfga,infisical,lago,openmeter,signoz"
DATABASES_CONFIG="${POSTGRES_MULTIPLE_DATABASES:-openfga,infisical,lago,openmeter,signoz}"

if [ -n "$DATABASES_CONFIG" ]; then
  echo "[init-multi-db] Processing multi-database configuration..."
  IFS=',' read -ra ENTRIES <<< "$DATABASES_CONFIG"
  for entry in "${ENTRIES[@]}"; do
    entry=$(echo "$entry" | xargs)
    if [ -z "$entry" ]; then
      continue
    fi
    IFS=':' read -ra PARTS <<< "$entry"
    DB_NAME="${PARTS[0]}"
    DB_USER="${PARTS[1]:-$DB_NAME}"
    DB_PASS="${PARTS[2]:-$DB_NAME}"
    create_db_and_user "$DB_NAME" "$DB_USER" "$DB_PASS"
  done
  echo "[init-multi-db] All consolidated multi-tenant databases ready."
fi
