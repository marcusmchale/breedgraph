#!/bin/bash
# Dumps DATABASE_NAME to NEO4J_ARCHIVE_PATH as <database>-<date>.dump.age, encrypted with age to the public key
# ENCRYPTION_RECIPIENT (docs/backups.md, Encryption key), so no unencrypted dump is written.
# Without a key it writes an unencrypted <database>-<date>.dump, which only ENVIRONMENT=development allows.
set -eo pipefail

DATE=$(date +%Y%m%d-%H%M%S)
NEO4J_STOPPED=0

if [ -n "${ENCRYPTION_RECIPIENT}" ]; then
    BACKUP="${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}-${DATE}.dump.age"
    # The archive server copies only complete dumps, so the dump is renamed once written
    PARTIAL="${BACKUP}.partial"
elif [ "${ENVIRONMENT}" = "development" ]; then
    echo "ENCRYPTION_RECIPIENT is not set, so the dump is not encrypted (ENVIRONMENT is development)"
    BACKUP="${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}-${DATE}.dump"
    PARTIAL=""
else
    echo "ENCRYPTION_RECIPIENT is required: the age public key that backups are encrypted to (README, \"Encryption key\")"
    exit 1
fi

cleanup() {
    if [ -n "${PARTIAL}" ]; then
        rm -f "${PARTIAL}"
    fi
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
if [ -n "${ENCRYPTION_RECIPIENT}" ]; then
    sudo -u neo4j neo4j-admin database dump \
        "${DATABASE_NAME}" \
        --to-stdout \
        | age --encrypt --recipient "${ENCRYPTION_RECIPIENT}" --output "${PARTIAL}"
    mv "${PARTIAL}" "${BACKUP}"
else
    sudo -u neo4j neo4j-admin database dump \
        "${DATABASE_NAME}" \
        --to-path="${NEO4J_ARCHIVE_PATH}"

    echo "Renaming backup..."
    sudo -u neo4j mv \
        "${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump" \
        "${BACKUP}"
fi

echo "Starting Neo4j..."
sudo service neo4j start
NEO4J_STOPPED=0

echo "Backup complete:"
echo "${BACKUP}"
