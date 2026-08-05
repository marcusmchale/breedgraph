#!/bin/bash
set -e

NEO4J_ARCHIVE_PATH="/home/marcus/PycharmProjects/breedgraph/instance/neo4j_archive"
DATABASE_NAME="neo4j"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-filename>"
    exit 1
fi

BACKUP_FILE="$1"
BACKUP_PATH="${NEO4J_ARCHIVE_PATH/}/${BACKUP_FILE}"
TEMP_DUMP="${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump"

if [ ! -f "$BACKUP_PATH" ]; then
    echo "Backup file not found:"
    echo "$BACKUP_PATH"
    exit 1
fi

echo "WARNING: This will overwrite database '${DATABASE_NAME}'."
echo "Backup:"
echo "${BACKUP_PATH}"

read -r -p "Continue? Type 'yes' to proceed: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 1
fi

NEO4J_STOPPED=0

cleanup() {
    if [ "$NEO4J_STOPPED" -eq 1 ]; then
        echo "Restarting Neo4j..."
        sudo service neo4j start
    fi
    if [ -f "${TEMP_DUMP}" ]; then
        echo "Removing temporary dump file..."
        sudo -u neo4j rm -f "${TEMP_DUMP}"
    fi
}

trap cleanup EXIT

echo "Stopping Neo4j..."
sudo service neo4j stop
NEO4J_STOPPED=1

echo "Copying backup to temporary path for restoration: ${TEMP_DUMP}"
sudo -u neo4j cp ${BACKUP_PATH} ${TEMP_DUMP}

echo "Restoring backup: ${TEMP_DUMP}"
sudo -u neo4j neo4j-admin database load \
    "${DATABASE_NAME}" \
    --from-path="${NEO4J_ARCHIVE_PATH}" \
    --overwrite-destination=true

echo "Starting Neo4j..."
sudo service neo4j start
NEO4J_STOPPED=0

echo "Removing temporary dump file ${TEMP_DUMP}"
sudo -u neo4j rm ${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump

echo "Restore complete."