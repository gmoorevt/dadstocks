#!/bin/bash

# Copyright (c) 2024 gmoorevt
# Dad's Stocks Dashboard Deployment Script for Proxmox VE
set -euo pipefail
shopt -s inherit_errexit nullglob

# Set version
APP_VERSION="v1.0.0-alpha"
GITHUB_REPO="https://github.com/gmoorevt/dadstocks"
DOWNLOAD_URL="https://github.com/gmoorevt/dadstocks/archive/refs/tags/${APP_VERSION}.tar.gz"
DEBUG=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
RESET='\033[0m'

# Fancy progress indicators
CHECKMARK='\033[0;32m\xE2\x9C\x94\033[0m'
CROSS='\033[0;31m\xE2\x9C\x98\033[0m'
INFO='\033[0;33m\xE2\x84\xB9\033[0m'

# Variables
TEMP_DIR=$(mktemp -d)
CONTAINER_ID=""

# Cleanup function
cleanup() {
    local exit_code=$?
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
    if [ -n "$CONTAINER_ID" ] && [ $exit_code -ne 0 ]; then
        msg_info "Cleaning up failed installation..."
        if pct status $CONTAINER_ID &>/dev/null; then
            pct stop $CONTAINER_ID &>/dev/null
            pct destroy $CONTAINER_ID &>/dev/null
        fi
        msg_ok "Cleanup completed"
    fi
    if [ $exit_code -ne 0 ]; then
        msg_error "Installation failed! Please check the error messages above."
    fi
    exit $exit_code
}

# Set up cleanup trap
trap cleanup EXIT ERR

# Header function
header_info() {
    clear
    echo -e "${CYAN}
    ╔═══════════════════════════════════════════════════════════════╗
    ║                   Dad's Stocks Dashboard                       ║
    ║                   Proxmox VE Installer                        ║
    ╚═══════════════════════════════════════════════════════════════╝${RESET}"
    echo -e "\n This script will create a LXC container running Dad's Stocks Dashboard.\n"
}

# Message functions
msg_info() {
    local msg="$1"
    echo -e "${INFO} ${CYAN}$msg${RESET}"
}

msg_ok() {
    local msg="$1"
    echo -e "${CHECKMARK} ${GREEN}$msg${RESET}"
}

msg_error() {
    local msg="$1"
    echo -e "${CROSS} ${RED}$msg${RESET}"
}

msg_debug() {
    if [ "$DEBUG" = true ]; then
        local msg="$1"
        echo -e "${YELLOW}DEBUG: $msg${RESET}"
    fi
}

# Check if debug mode is enabled
if [ "${DEBUG_SCRIPT:-false}" = "true" ]; then
    DEBUG=true
    set -x  # Enable command tracing
    msg_info "Debug mode enabled"
fi

# Check if script is running on Proxmox
if [ ! -f "/etc/pve/local/pve-ssl.key" ]; then
    msg_error "This script must be run on a Proxmox host"
    exit 1
fi

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    msg_error "Please run as root"
    exit 1
fi

# Check for required tools
for cmd in pct wget curl; do
    if ! command -v $cmd >/dev/null 2>&1; then
        msg_error "$cmd is required but not installed"
        exit 1
    fi
done

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

# Function to get user input with validation
get_input() {
    local prompt=$1
    local validate_func=$2
    local default_value=$3
    local value=""
    
    while true; do
        if [ -n "$default_value" ]; then
            read -p "$(echo -e "${BLUE}$prompt [$default_value]: ${RESET}")" value
            if [ -z "$value" ]; then
                value=$default_value
            fi
        else
            read -p "$(echo -e "${BLUE}$prompt: ${RESET}")" value
        fi
        
        if [ -n "$validate_func" ]; then
            if $validate_func "$value"; then
                break
            else
                msg_error "Invalid input. Please try again."
            fi
        else
            if [ -n "$value" ]; then
                break
            else
                msg_error "Input cannot be empty. Please try again."
            fi
        fi
    done
    echo "$value"
}

# Display header
header_info

# Check for Ubuntu template
msg_info "Checking for Ubuntu 22.04 LXC template..."
TEMPLATE_PATH="/var/lib/vz/template/cache/ubuntu-22.04-standard_22.04-1_amd64.tar.gz"
if [ ! -f "$TEMPLATE_PATH" ]; then
    msg_info "Downloading Ubuntu 22.04 LXC template..."
    if ! pveam update >/dev/null 2>&1; then
        msg_error "Failed to update template list"
        msg_debug "Error updating template list. Try running 'pveam update' manually"
        exit 1
    fi
    
    # List available templates for debugging
    if [ "$DEBUG" = true ]; then
        msg_debug "Available templates:"
        pveam available | grep -i ubuntu
    fi
    
    # Try to download the template
    if ! pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.gz 2>&1; then
        msg_error "Failed to download Ubuntu template"
        msg_debug "Template download failed. Verify template name with 'pveam available'"
        msg_debug "You can try downloading manually with:"
        msg_debug "pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.gz"
        exit 1
    fi
    
    # Verify the download
    if [ ! -f "$TEMPLATE_PATH" ]; then
        msg_error "Template download appeared to succeed but file is missing"
        msg_debug "Expected template at: $TEMPLATE_PATH"
        msg_debug "Check storage configuration and permissions"
        exit 1
    fi
fi
msg_ok "Ubuntu 22.04 LXC template is available"

# Get configuration values
echo -e "\n${MAGENTA}Container Configuration${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
CONTAINER_ID=$(get_input "Enter Container ID" "" "1000")
CT_ID=$CONTAINER_ID
CT_HOSTNAME=$(get_input "Enter Container Hostname" "" "dadstocks")
CT_PASSWORD=$(openssl rand -base64 32)

echo -e "\n${MAGENTA}Resource Configuration${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
CT_MEMORY=$(get_input "Enter Memory Size in MB" "" "2048")
CT_SWAP=$(get_input "Enter Swap Size in MB" "" "512")
CT_STORAGE=$(get_input "Enter Storage Location" "" "local-lvm")

echo -e "\n${MAGENTA}Network Configuration${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
CT_NETWORK_IP=$(get_input "Enter Container IP (CIDR format, e.g., 192.168.1.100/24)" validate_ip "")
CT_NETWORK_GW=$(get_input "Enter Gateway IP" validate_gateway "")

# Create LXC container
msg_info "Creating LXC container..."
pct create $CT_ID $TEMPLATE_PATH \
    --hostname $CT_HOSTNAME \
    --memory $CT_MEMORY \
    --swap $CT_SWAP \
    --storage $CT_STORAGE \
    --net0 name=eth0,bridge=vmbr0,ip=$CT_NETWORK_IP,gw=$CT_NETWORK_GW \
    --password $CT_PASSWORD \
    --unprivileged 1 \
    --features nesting=1 \
    --start 1 >/dev/null 2>&1

# Wait for container to start
msg_info "Waiting for container to start..."
sleep 10

# Install dependencies
msg_info "Installing dependencies..."
pct exec $CT_ID -- bash -c "apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    python3-pip \
    python3-venv \
    nginx" >/dev/null 2>&1
msg_ok "Dependencies installed"

# Install Docker
msg_info "Installing Docker..."
pct exec $CT_ID -- bash -c "curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    systemctl enable docker && \
    systemctl start docker" >/dev/null 2>&1
msg_ok "Docker installed"

# Install Docker Compose
msg_info "Installing Docker Compose..."
pct exec $CT_ID -- bash -c "curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose" >/dev/null 2>&1
msg_ok "Docker Compose installed"

# Deploy application
msg_info "Deploying application..."
if ! run_in_container $CT_ID "mkdir -p /opt/dadstocks && \
    cd /opt/dadstocks && \
    wget -q ${DOWNLOAD_URL} -O app.tar.gz && \
    tar xzf app.tar.gz --strip-components=1 && \
    rm app.tar.gz" "Failed to deploy application"; then
    msg_debug "Failed to download from: ${DOWNLOAD_URL}"
    exit 1
fi
msg_ok "Application deployed"

# Get Alpaca API credentials
echo -e "\n${MAGENTA}Alpaca API Configuration${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
ALPACA_API_KEY=$(get_input "Enter Alpaca API Key" "" "")
ALPACA_SECRET_KEY=$(get_input "Enter Alpaca Secret Key" "" "")

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Configure application
msg_info "Configuring application..."
if ! run_in_container $CT_ID "cat > /opt/dadstocks/.env << EOL
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=$SECRET_KEY
SIMULATION_MODE=false
DATABASE_URL=sqlite:///stocks.db
ALPACA_API_KEY=$ALPACA_API_KEY
ALPACA_SECRET_KEY=$ALPACA_SECRET_KEY
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
EOL" "Failed to create .env file"; then
    exit 1
fi

# Configure Nginx
msg_info "Configuring Nginx..."
if ! run_in_container $CT_ID "cat > /etc/nginx/sites-available/dadstocks << EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
    }
}
EOL" "Failed to create Nginx configuration"; then
    exit 1
fi

if ! run_in_container $CT_ID "ln -sf /etc/nginx/sites-available/dadstocks /etc/nginx/sites-enabled/ && \
    rm -f /etc/nginx/sites-enabled/default && \
    systemctl restart nginx" "Failed to enable Nginx configuration"; then
    exit 1
fi
msg_ok "Nginx configured"

# Start application
msg_info "Starting application..."
if ! run_in_container $CT_ID "cd /opt/dadstocks && docker-compose up -d" "Failed to start application"; then
    msg_debug "Docker Compose failed. Checking Docker status..."
    run_in_container $CT_ID "systemctl status docker" "Unable to check Docker status"
    run_in_container $CT_ID "docker ps" "Unable to list Docker containers"
    exit 1
fi
msg_ok "Application started"

# Verify application is accessible
msg_info "Verifying application..."
sleep 5
if ! run_in_container $CT_ID "curl -s -f http://localhost:5001/" "Application is not responding"; then
    msg_debug "Application failed to respond. Checking logs..."
    run_in_container $CT_ID "docker-compose -f /opt/dadstocks/docker-compose.yml logs" "Unable to fetch logs"
    exit 1
fi
msg_ok "Application is running"

# Print completion message
echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║                   Installation Complete!                        ║${RESET}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${RESET}\n"

echo -e "${YELLOW}Important Information:${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
echo -e "Application URL: http://${CT_NETWORK_IP%/*}"
echo -e "Container ID: $CT_ID"
echo -e "Container Password: $CT_PASSWORD"
echo -e "Admin Username: admin"
echo -e "Admin Password: $ADMIN_PASSWORD"

echo -e "\n${YELLOW}Useful Commands:${RESET}"
echo -e "${CYAN}────────────────────────${RESET}"
echo -e "View application logs:"
echo -e "  pct exec $CT_ID -- docker-compose -f /opt/dadstocks/docker-compose.yml logs -f"
echo -e "\nView Nginx logs:"
echo -e "  pct exec $CT_ID -- tail -f /var/log/nginx/access.log"
echo -e "  pct exec $CT_ID -- tail -f /var/log/nginx/error.log"

echo -e "\n${MAGENTA}Please save this information for future reference!${RESET}\n" 