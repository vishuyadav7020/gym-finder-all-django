# Docker Setup for Gym Finder Django Backend

This document explains how to build and run the Gym Finder Django backend application using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose installed (usually comes with Docker Desktop)

## Files Overview

- **Dockerfile**: Multi-stage build configuration for Django application
- **docker-compose.yml**: Orchestration file for Django + MongoDB + Nginx
- **nginx.conf**: Nginx reverse proxy configuration
- **.dockerignore**: Files to exclude from Docker build context
- **requirements.txt**: Python dependencies
- **.env.example**: Environment variables template

## Quick Start

### 1. Setup Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and update with your values
# Important: Change SECRET_KEY and MONGO_PASSWORD in production!
```

### 2. Build and Run with Docker Compose

```bash
# Build and start all services (Django + MongoDB + Nginx)
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f mongodb
docker-compose logs -f nginx

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This deletes database data)
docker-compose down -v
```

The application will be available at:
- **API**: http://localhost (via Nginx on port 80)
- **Direct Backend**: http://localhost:8000
- **MongoDB**: localhost:27017

## Services

### 1. MongoDB (Database)
- **Container**: gym-finder-mongodb
- **Port**: 27017
- **Credentials**: Set in docker-compose.yml
- **Data**: Persisted in Docker volume `mongodb_data`

### 2. Django Backend
- **Container**: gym-finder-backend
- **Port**: 8000
- **Framework**: Django 5.0 + DRF
- **Server**: Gunicorn with 3 workers
- **Database**: MongoDB

### 3. Nginx (Reverse Proxy)
- **Container**: gym-finder-nginx
- **Port**: 80
- **Purpose**: Reverse proxy, static/media files serving
- **Features**: CORS, compression, caching, security headers

## Development vs Production

### Development Mode

For development with hot reload:

```bash
# Run Django dev server locally (not in Docker)
python manage.py runserver
```

Or create a `docker-compose.dev.yml`:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: HeroHonda@211202
    volumes:
      - mongodb_data:/data/db

  backend:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - DJANGO_ENV=local
    depends_on:
      - mongodb

volumes:
  mongodb_data:
```

Run with: `docker-compose -f docker-compose.dev.yml up`

### Production Mode

The default `docker-compose.yml` is configured for production with:
- Gunicorn WSGI server
- Nginx reverse proxy
- Security headers
- Static file serving
- MongoDB with persistent storage

## Common Commands

### Django Management Commands

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput

# Django shell
docker-compose exec backend python manage.py shell

# Run custom management command
docker-compose exec backend python manage.py <command>
```

### Database Operations

```bash
# Access MongoDB shell
docker-compose exec mongodb mongosh -u admin -p HeroHonda@211202

# Backup database
docker-compose exec mongodb mongodump --uri="mongodb://admin:HeroHonda@211202@localhost:27017/gym_finder_management_db?authSource=admin" --out=/backup

# Restore database
docker-compose exec mongodb mongorestore --uri="mongodb://admin:HeroHonda@211202@localhost:27017/gym_finder_management_db?authSource=admin" /backup
```

### Container Management

```bash
# View running containers
docker-compose ps

# Restart a service
docker-compose restart backend

# Rebuild a service
docker-compose up -d --build backend

# View resource usage
docker stats

# Execute command in container
docker-compose exec backend sh

# View nginx access logs
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

## Environment Variables

Key environment variables in `.env`:

```bash
# Django
DJANGO_ENV=production          # Environment: local, production
DEBUG=false                    # Debug mode (never true in production!)
SECRET_KEY=your-secret-key     # Django secret key (change this!)

# MongoDB
MONGO_URI=mongodb://...        # Full MongoDB connection string
MONGO_DB_NAME=gym_finder_management_db
MONGO_HOST=mongodb             # Service name in docker-compose
MONGO_PORT=27017

# API
VITE_API_BASE_URL=http://localhost:8000

# Security
ALLOWED_HOSTS=localhost,your-domain.com
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## Nginx Configuration

The nginx.conf provides:

- **Reverse Proxy**: Forwards requests to Django backend
- **Static Files**: Serves `/static/` from `/app/staticfiles/`
- **Media Files**: Serves `/media/` from `/app/media/`
- **CORS**: Configured for API endpoints
- **Compression**: Gzip enabled for text files
- **Caching**: 1-year cache for static/media files
- **Security Headers**: X-Frame-Options, X-XSS-Protection, etc.
- **Health Check**: `/health/` endpoint

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs backend

# Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database connection issues

```bash
# Check MongoDB is running
docker-compose ps mongodb

# Test MongoDB connection
docker-compose exec mongodb mongosh -u admin -p HeroHonda@211202

# Check backend can reach MongoDB
docker-compose exec backend ping mongodb
```

### Static files not loading

```bash
# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput

# Check nginx volume mount
docker-compose exec nginx ls -la /app/staticfiles

# Restart nginx
docker-compose restart nginx
```

### Permission issues

```bash
# Fix media directory permissions
docker-compose exec backend chown -R www-data:www-data /app/media

# Fix static files permissions
docker-compose exec backend chown -R www-data:www-data /app/staticfiles
```

## Production Deployment

### Security Checklist

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=false`
- [ ] Update `ALLOWED_HOSTS` with your domain
- [ ] Change MongoDB password
- [ ] Use environment-specific `.env` files
- [ ] Enable HTTPS (use Let's Encrypt)
- [ ] Set up proper backup strategy
- [ ] Configure firewall rules
- [ ] Use Docker secrets for sensitive data
- [ ] Enable MongoDB authentication
- [ ] Set up monitoring and logging

### HTTPS with Let's Encrypt

Update nginx.conf for HTTPS:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # ... rest of configuration
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Scaling

To scale the backend:

```bash
# Run 3 backend instances
docker-compose up -d --scale backend=3

# Update nginx upstream for load balancing
```

## Backup Strategy

### Automated Backups

Create a backup script:

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/$DATE"

# Backup MongoDB
docker-compose exec -T mongodb mongodump \
  --uri="mongodb://admin:HeroHonda@211202@localhost:27017/gym_finder_management_db?authSource=admin" \
  --out=$BACKUP_DIR

# Backup media files
docker cp gym-finder-backend:/app/media $BACKUP_DIR/media

echo "Backup completed: $BACKUP_DIR"
```

Schedule with cron:
```bash
0 2 * * * /path/to/backup.sh
```

## Monitoring

### Health Checks

```bash
# Check backend health
curl http://localhost/health/

# Check API
curl http://localhost/api/org/gym/public/list/

# Check MongoDB
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

### Logs

```bash
# Follow all logs
docker-compose logs -f

# Export logs
docker-compose logs > logs.txt

# View last 100 lines
docker-compose logs --tail=100 backend
```

## Integration with Frontend

To connect with the React frontend:

```yaml
version: '3.8'

services:
  frontend:
    build: ../gym-finder-near-you
    ports:
      - "3000:80"
    depends_on:
      - nginx
    networks:
      - gym-finder-network

  # ... existing services (backend, mongodb, nginx)

networks:
  gym-finder-network:
    driver: bridge
```

Update frontend API URL to point to nginx: `http://nginx:80`

## Useful Resources

- [Django Docker Best Practices](https://docs.docker.com/samples/django/)
- [MongoDB Docker Documentation](https://hub.docker.com/_/mongo)
- [Nginx Docker Documentation](https://hub.docker.com/_/nginx)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
