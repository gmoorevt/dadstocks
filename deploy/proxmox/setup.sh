#!/bin/bash

# Proxmox deployment script for Dad's Stocks Dashboard
# This script should be run on the Proxmox host

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
GITHUB_REPO="https://github.com/gmoorevt/dadstocks.git"
APP_VERSION="v1.0.0-alpha"

# Function to print colored text
print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# Function to validate IP address
validate_ip() {
    local ip=$1
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to validate gateway IP
validate_gateway() {
    local ip=$1
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to validate numeric input
validate_numeric() {
    local num=$1
    if [[ $num =~ ^[0-9]+$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to get user input with validation
get_input() {
    local prompt=$1
    local validate_func=$2
    local default_value=$3
    local value=""
    
    while true; do
        if [ -n "$default_value" ]; then
            read -p "$(print_color $BLUE "$prompt [$default_value]: ")" value
            if [ -z "$value" ]; then
                value=$default_value
            fi
        else
            read -p "$(print_color $BLUE "$prompt: ")" value
        fi
        
        if [ -n "$validate_func" ]; then
            if $validate_func "$value"; then
                break
            else
                print_color $RED "Invalid input. Please try again."
            fi
        else
            if [ -n "$value" ]; then
                break
            else
                print_color $RED "Input cannot be empty. Please try again."
            fi
        fi
    done
    echo "$value"
}

# Check if running on Proxmox
if [ ! -f "/etc/pve/local/pve-ssl.key" ]; then
    print_color $RED "Error: This script must be run on a Proxmox host"
    exit 1
fi

print_color $GREEN "Welcome to Dad's Stocks Dashboard Deployment Script!"
echo
print_color $YELLOW "This script will help you set up the application in a Proxmox container."
echo

# Get configuration values
print_color $GREEN "Container Configuration"
echo "--------------------------------"
CT_ID=$(get_input "Enter Container ID" validate_numeric "1000")
CT_HOSTNAME=$(get_input "Enter Container Hostname" "" "dadstocks")
CT_PASSWORD=$(get_input "Enter Container Root Password" "" "")

echo
print_color $GREEN "Resource Configuration"
echo "--------------------------------"
CT_MEMORY=$(get_input "Enter Memory Size in MB" validate_numeric "2048")
CT_SWAP=$(get_input "Enter Swap Size in MB" validate_numeric "512")
CT_STORAGE=$(get_input "Enter Storage Location" "" "local-lvm")

echo
print_color $GREEN "Network Configuration"
echo "--------------------------------"
CT_NETWORK_IP=$(get_input "Enter Container IP (CIDR format, e.g., 192.168.1.100/24)" validate_ip "")
CT_NETWORK_GW=$(get_input "Enter Gateway IP" validate_gateway "")

# Confirm settings
echo
print_color $GREEN "Please review your settings:"
echo "--------------------------------"
echo "Container ID: $CT_ID"
echo "Hostname: $CT_HOSTNAME"
echo "Memory: $CT_MEMORY MB"
echo "Swap: $CT_SWAP MB"
echo "Storage: $CT_STORAGE"
echo "IP Address: $CT_NETWORK_IP"
echo "Gateway: $CT_NETWORK_GW"
echo

read -p "$(print_color $YELLOW "Do you want to proceed with these settings? [y/N] ")" confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    print_color $RED "Deployment cancelled."
    exit 1
fi

# Create LXC container
print_color $GREEN "Creating LXC container..."
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

if [ $? -ne 0 ]; then
    print_color $RED "Failed to create container. Please check your settings and try again."
    exit 1
fi

# Wait for container to start
print_color $GREEN "Waiting for container to start..."
sleep 10

# Install required packages
print_color $GREEN "Installing required packages..."
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

if [ $? -ne 0 ]; then
    print_color $RED "Failed to install required packages."
    exit 1
fi

# Install Docker
print_color $GREEN "Installing Docker..."
pct exec $CT_ID -- bash -c "curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    systemctl enable docker && \
    systemctl start docker"

if [ $? -ne 0 ]; then
    print_color $RED "Failed to install Docker."
    exit 1
fi

# Install Docker Compose
print_color $GREEN "Installing Docker Compose..."
pct exec $CT_ID -- bash -c "curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose"

if [ $? -ne 0 ]; then
    print_color $RED "Failed to install Docker Compose."
    exit 1
fi

# Create app directory
print_color $GREEN "Setting up application..."
pct exec $CT_ID -- bash -c "mkdir -p /opt/dadstocks"

# Clone repository
print_color $GREEN "Cloning repository..."
pct exec $CT_ID -- bash -c "cd /opt/dadstocks && \
    git clone $GITHUB_REPO . && \
    git checkout $APP_VERSION"

if [ $? -ne 0 ]; then
    print_color $RED "Failed to clone repository."
    exit 1
fi

# Get Alpaca API credentials
echo
print_color $GREEN "Alpaca API Configuration"
echo "--------------------------------"
ALPACA_API_KEY=$(get_input "Enter Alpaca API Key" "" "")
ALPACA_SECRET_KEY=$(get_input "Enter Alpaca Secret Key" "" "")

# Generate random values
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Create environment file
print_color $GREEN "Creating environment file..."
pct exec $CT_ID -- bash -c "cat > /opt/dadstocks/.env << EOL
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=$SECRET_KEY
SIMULATION_MODE=false
DATABASE_URL=sqlite:///stocks.db
ALPACA_API_KEY=$ALPACA_API_KEY
ALPACA_SECRET_KEY=$ALPACA_SECRET_KEY
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
EOL"

# Set up Nginx
print_color $GREEN "Configuring Nginx..."
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

if [ $? -ne 0 ]; then
    print_color $RED "Failed to configure Nginx."
    exit 1
fi

# Start application
print_color $GREEN "Starting application..."
pct exec $CT_ID -- bash -c "cd /opt/dadstocks && \
    docker-compose up -d"

if [ $? -ne 0 ]; then
    print_color $RED "Failed to start application."
    exit 1
fi

# Print completion message
print_color $GREEN "Deployment completed successfully!"
echo
print_color $YELLOW "Important Information:"
echo "--------------------------------"
echo "1. Application URL: http://${CT_NETWORK_IP%/*}"
echo "2. Admin Username: admin"
echo "3. Admin Password: $ADMIN_PASSWORD"
echo
print_color $BLUE "Useful Commands:"
echo "--------------------------------"
echo "View application logs:"
echo "  pct exec $CT_ID -- docker-compose -f /opt/dadstocks/docker-compose.yml logs -f"
echo
echo "View Nginx logs:"
echo "  pct exec $CT_ID -- tail -f /var/log/nginx/access.log"
echo "  pct exec $CT_ID -- tail -f /var/log/nginx/error.log"
echo
print_color $YELLOW "Please save this information for future reference!" 