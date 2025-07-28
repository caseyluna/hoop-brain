#!/bin/bash
set -e
host="${1:-db}"
until pg_isready -h "$host" -p 5432; do
  echo "Waiting for Postgres at $host:5432..."
  sleep 1
done
echo "Postgres is up!"
exec "${@:2}"
