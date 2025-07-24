#!/bin/bash
"""
Simple deployment script for Vacation Manager
"""

set -e

echo "🚀 Deploying Vacation Manager with Docker..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.docker .env
    echo "📝 Please edit .env file and set your SECRET_KEY and other configuration"
    echo "💡 Generate a secret key with: python -c 'import secrets; print(secrets.token_hex(32))'"
    echo ""
    read -p "Press Enter to continue after editing .env file..."
fi

# Create directories
echo "📁 Creating data directories..."
mkdir -p data logs

# Build and start
echo "🔨 Building and starting containers..."
docker-compose up -d --build

# Wait for health check
echo "⏳ Waiting for application to be ready..."
sleep 10

# Check health
echo "🏥 Checking application health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Application is healthy!"
    echo ""
    echo "🎉 Deployment successful!"
    echo "📱 Application: http://localhost:8000"
    echo "🏥 Health Check: http://localhost:8000/health"
    echo "📊 View logs: docker-compose logs -f"
    echo "🛑 Stop: docker-compose down"
else
    echo "❌ Application health check failed"
    echo "📋 Check logs: docker-compose logs"
    exit 1
fi
