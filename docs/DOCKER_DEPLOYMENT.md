# Docker Deployment Guide

## Overview
This guide explains how to deploy the Vacation Manager application using Docker, which provides a production-ready environment without the Flask development server warnings.

## Quick Start

### 1. **Prepare Environment**
```bash
# Copy the environment template
cp .env.docker .env

# Edit the environment file
nano .env
```

**Important**: Change the `SECRET_KEY` to a secure random value:
```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. **Build and Run**
```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f vacation-manager

# Check status
docker-compose ps
```

### 3. **Access Application**
- Application: http://localhost:8000
- Health Check: http://localhost:8000/health

## Configuration

### **Environment Variables**
Edit `.env` file with your configuration:

```env
# Security - REQUIRED!
SECRET_KEY=your-super-secret-key-change-this-immediately

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=false

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Email Configuration
USE_FILE_EMAIL=true
FROM_EMAIL=noreply@your-domain.com
FROM_NAME=Vacation Manager

# Database Configuration
DB_PATH=/app/data/user.db

# Logging
LOG_LEVEL=INFO
```

### **Optional: Slack Integration**
```env
VACATION_ADDED_WEBHOOK_URL=https://hooks.slack.com/workflows/...
VACATION_DELETED_WEBHOOK_URL=https://hooks.slack.com/workflows/...
```

## Production Features

### **Production Server**
- ✅ **Gunicorn WSGI Server**: No more development server warnings
- ✅ **Multi-worker**: 4 worker processes for better performance
- ✅ **Health Checks**: Built-in health monitoring
- ✅ **Proper Logging**: Structured logging to stdout/stderr

### **Security**
- ✅ **Non-root User**: Application runs as non-privileged user
- ✅ **Minimal Image**: Based on Python slim image
- ✅ **Environment Isolation**: Containerized environment

### **Reliability**
- ✅ **Auto-restart**: Container restarts on failure
- ✅ **Health Monitoring**: Docker health checks
- ✅ **Persistent Data**: Database stored in Docker volume

## Docker Commands

### **Basic Operations**
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### **Database Management**
```bash
# Access database container
docker-compose exec vacation-manager bash

# Backup database
docker-compose exec vacation-manager cp /app/data/user.db /app/data/backup-$(date +%Y%m%d).db

# View database files
docker-compose exec vacation-manager ls -la /app/data/
```

### **Maintenance**
```bash
# Update application
docker-compose pull
docker-compose up -d --build

# Clean up old images
docker system prune -f

# View resource usage
docker stats
```

## Advanced Configuration

### **With Nginx Reverse Proxy**
```bash
# Start with nginx
docker-compose --profile with-nginx up -d
```

This adds:
- Nginx reverse proxy on port 80/443
- SSL termination support
- Static file serving
- Load balancing capabilities

### **Custom Nginx Configuration**
Create `nginx.conf`:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream vacation-manager {
        server vacation-manager:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://vacation-manager;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://vacation-manager/health;
            access_log off;
        }
    }
}
```

## Monitoring

### **Health Checks**
```bash
# Check application health
curl http://localhost:8000/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2025-07-23T10:00:00",
  "version": "1.0.0"
}
```

### **Logs**
```bash
# Application logs
docker-compose logs vacation-manager

# Follow logs in real-time
docker-compose logs -f vacation-manager

# Filter logs by level
docker-compose logs vacation-manager | grep ERROR
```

### **Resource Monitoring**
```bash
# Container resource usage
docker stats vacation-manager

# Disk usage
docker system df

# Container details
docker inspect vacation-manager
```

## Backup and Recovery

### **Database Backup**
```bash
# Create backup
docker-compose exec vacation-manager cp /app/data/user.db /app/data/backup-$(date +%Y%m%d-%H%M%S).db

# Copy backup to host
docker cp $(docker-compose ps -q vacation-manager):/app/data/backup-*.db ./backups/
```

### **Full Backup**
```bash
# Backup data directory
tar -czf vacation-manager-backup-$(date +%Y%m%d).tar.gz data/

# Backup configuration
cp .env .env.backup
```

### **Recovery**
```bash
# Stop services
docker-compose down

# Restore data
tar -xzf vacation-manager-backup-YYYYMMDD.tar.gz

# Start services
docker-compose up -d
```

## Troubleshooting

### **Common Issues**

#### **Port Already in Use**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Use different port
echo "PORT=8001" >> .env
docker-compose up -d
```

#### **Permission Issues**
```bash
# Fix data directory permissions
sudo chown -R 1000:1000 data/
```

#### **Database Issues**
```bash
# Reset database
docker-compose down
rm -rf data/user.db
docker-compose up -d
```

#### **Container Won't Start**
```bash
# Check logs
docker-compose logs vacation-manager

# Check configuration
docker-compose config

# Rebuild container
docker-compose up -d --build --force-recreate
```

### **Performance Tuning**

#### **Adjust Workers**
```yaml
# In docker-compose.yml
command: ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "8", "--timeout", "120", "app:app"]
```

#### **Memory Limits**
```yaml
# In docker-compose.yml
services:
  vacation-manager:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

## Security Considerations

### **Production Checklist**
- [ ] Change default SECRET_KEY
- [ ] Use strong passwords for user accounts
- [ ] Enable HTTPS with SSL certificates
- [ ] Configure firewall rules
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity
- [ ] Backup data regularly
- [ ] Use environment-specific configurations

### **SSL/HTTPS Setup**
```bash
# Generate SSL certificates (Let's Encrypt example)
certbot certonly --standalone -d your-domain.com

# Update nginx configuration for HTTPS
# Add SSL certificates to docker-compose.yml volumes
```

## Conclusion

Docker deployment provides a production-ready environment that:
- ✅ Eliminates Flask development server warnings
- ✅ Provides proper WSGI server (Gunicorn)
- ✅ Ensures consistent deployment across environments
- ✅ Simplifies scaling and maintenance
- ✅ Includes health monitoring and logging
- ✅ Supports easy backup and recovery

This setup is suitable for production use and can be easily scaled or integrated with orchestration platforms like Kubernetes if needed.
