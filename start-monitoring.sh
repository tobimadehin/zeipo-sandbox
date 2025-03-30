#!/bin/bash
# start-monitoring.sh

echo "Starting Zeipo Monitoring Infrastructure..."

# Ensure directories exist
mkdir -p prometheus/data
mkdir -p grafana/data
mkdir -p logs/calls

# Start the stack
docker-compose up -d prometheus grafana timescaledb

# Wait for services to be available
echo "Waiting for services to become available..."
sleep 10

# Check if services are running
prometheus_status=$(docker-compose ps -q prometheus)
grafana_status=$(docker-compose ps -q grafana)
timescaledb_status=$(docker-compose ps -q timescaledb)

if [ -z "$prometheus_status" ] || [ -z "$grafana_status" ] || [ -z "$timescaledb_status" ]; then
    echo "Error: One or more services failed to start. Check logs with 'docker-compose logs'"
    exit 1
else
    echo "✅ Monitoring infrastructure is up and running!"
    echo "🔍 Prometheus: http://localhost:9090"
    echo "📊 Grafana: http://localhost:3000 (admin/zeipo_analytics)"
    echo "💾 TimescaleDB running on port 5432"
fi