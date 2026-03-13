#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running. Start Docker Desktop or dockerd first."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  docker compose up -d postgres weaviate neo4j
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d postgres weaviate neo4j
else
  echo "docker compose is not available. Install the Docker Compose plugin or docker-compose."
  exit 1
fi

cat <<EOF

Memory services are starting.

Neo4j Browser: http://localhost:7474/browser/
Weaviate Schema: http://localhost:8080/v1/schema
Weaviate Objects: http://localhost:8080/v1/objects

Default Neo4j credentials:
  username: neo4j
  password: midasdevpassword
EOF
