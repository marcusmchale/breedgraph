. ./instance/envars.sh

services=(mailhog neo4j redis)
for service in "${services[@]}"; do
    if ! systemctl is-active --quiet "$service"; then
        echo "$service is not active"
        exit 1
    fi
done

python -m pytest tests --log-disable faker.factory