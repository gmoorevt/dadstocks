#!/bin/bash

# Proxmox deployment script for Dad's Stocks Dashboard
# This script should be run on the Proxmox host

# Configuration
CT_ID="1000"  # Container ID
CT_HOSTNAME="dadstocks"
CT_PASSWORD="your-secure-password"  # Change this
CT_MEMORY="2048"  # 2GB RAM
CT_SWAP="512"    # 512MB swap
CT_STORAGE="local-lvm"  # Storage location
CT_NETWORK_IP="192.168.1.100/24"  # Change this
CT_NETWORK_GW="192.168.1.1"      # Change this
GITHUB_REPO="https://github.com/gmoorevt/dadstocks.git"
APP_VERSION="v1.0.0-alpha"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting deployment of Dad's Stocks Dashboard...${NC}"

# Check if running on Proxmox
if [ ! -f "/etc/pve/local/pve-ssl.key" ]; then
    echo -e "${RED}Error: This script must be run on a Proxmox host${NC}"
    exit 1
fi

# Create LXC container
echo "Creating LXC container..."
pct create $CT_ID /var/lib/vz/template/cache/ubuntu-22.04-standard_22.04-1_amd64.tar.gz \
    --hostname $CT_HOSTNAME \
    --memory $CT_MEMORY \
    --swap $CT_SWAP \
    --storage $CT_STORAGE \
    --net0 name=eth0,bridge=vmbr0,ip=$CT_NETWORK_IP,gw=$CT_NETWORK_GW \
    --password $CT_PASSWORD \
    --unprivileged 1 \
    --features nesting=1 \
    --start 1

# Wait for container to start
echo "Waiting for container to start..."
sleep 10

# Install required packages
echo "Installing required packages..."
pct exec $CT_ID -- bash -c "apt-get update && \
    apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3-pip \
    python3-venv \
    nginx"

# Install Docker
echo "Installing Docker..."
pct exec $CT_ID -- bash -c "curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    systemctl enable docker && \
    systemctl start docker"

# Install Docker Compose
echo "Installing Docker Compose..."
pct exec $CT_ID -- bash -c "curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose"

# Create app directory
echo "Setting up application..."
pct exec $CT_ID -- bash -c "mkdir -p /opt/dadstocks"

# Clone repository
echo "Cloning repository..."
pct exec $CT_ID -- bash -c "cd /opt/dadstocks && \
    git clone $GITHUB_REPO . && \
    git checkout $APP_VERSION"

# Create environment file
echo "Creating environment file..."
pct exec $CT_ID -- bash -c "cat > /opt/dadstocks/.env << EOL
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=$(openssl rand -hex 32)
SIMULATION_MODE=false
DATABASE_URL=sqlite:///stocks.db
ALPACA_API_KEY=your-api-key
ALPACA_SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$(openssl rand -base64 12)
EOL"

# Set up Nginx
echo "Configuring Nginx..."
pct exec $CT_ID -- bash -c "cat > /etc/nginx/sites-available/dadstocks << EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL"

# Enable Nginx site
pct exec $CT_ID -- bash -c "ln -sf /etc/nginx/sites-available/dadstocks /etc/nginx/sites-enabled/ && \
    rm -f /etc/nginx/sites-enabled/default && \
    systemctl restart nginx"

# Start application
echo "Starting application..."
pct exec $CT_ID -- bash -c "cd /opt/dadstocks && \
    docker-compose up -d"

# Print completion message
echo -e "${GREEN}Deployment completed!${NC}"
echo "Please note the following:"
echo "1. Update the .env file with your Alpaca API credentials:"
echo "   pct exec $CT_ID -- nano /opt/dadstocks/.env"
echo "2. Access the application at: http://$CT_NETWORK_IP"
echo "3. Admin credentials are in the .env file"
echo "4. To view logs: pct exec $CT_ID -- docker-compose -f /opt/dadstocks/docker-compose.yml logs -f" 