#!/bin/bash
set -e

DATE=$(date +%Y%m%d-%H%M%S)
NEO4J_ARCHIVE_PATH="/home/marcus/PycharmProjects/breedgraph/instance/neo4j_archive"
DATABASE_NAME="neo4j"

NEO4J_STOPPED=0

cleanup() {
    if [ "$NEO4J_STOPPED" -eq 1 ]; then
        echo "Restarting Neo4j..."
        sudo service neo4j start
    fi
}

trap cleanup EXIT

echo "Stopping Neo4j..."
sudo service neo4j stop
NEO4J_STOPPED=1

echo "Creating backup..."
sudo -u neo4j neo4j-admin database dump \
    "${DATABASE_NAME}" \
    --to-path="${NEO4J_ARCHIVE_PATH}"

echo "Renaming backup..."
sudo -u neo4j mv \
    "${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump" \
    "${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}-${DATE}.dump"

echo "Starting Neo4j..."
sudo service neo4j start
NEO4J_STOPPED=0

echo "Backup complete:"
echo "${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}-${DATE}.dump"