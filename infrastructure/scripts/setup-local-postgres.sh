#!/bin/sh
# One-off local setup: creates the Postgres role + database this project's
# backend expects, for running the stack directly on this machine without
# Docker (Sprint 1 verification). Requires sudo (will prompt for your
# password) because creating roles/databases needs the postgres superuser.
#
# Run with:  ! sh infrastructure/scripts/setup-local-postgres.sh
set -e

sudo -u postgres psql -c "CREATE USER stackerbee WITH PASSWORD 'devpassword' CREATEDB;"
sudo -u postgres createdb -O stackerbee stackerbee_tender

echo "Done: role 'stackerbee' and database 'stackerbee_tender' created."
