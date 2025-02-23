# Proxmox Deployment Guide

This guide explains how to deploy Dad's Stocks Dashboard in a production environment using Proxmox VE.

## Quick Installation

Copy and paste this line into your Proxmox shell:

```bash
bash -c "$(wget -qLO - https://github.com/gmoorevt/dadstocks/raw/main/deploy/proxmox/setup.sh)"
```

## Prerequisites

- Proxmox VE 7.0 or later
- Ubuntu 22.04 LXC template downloaded in Proxmox
- Network connectivity
- Alpaca API credentials

## Quick Start

1. Copy the `setup.sh` script to your Proxmox host:
   ```bash
   scp setup.sh root@your-proxmox-host:/root/
   ```

2. Make the script executable and run it:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. Follow the interactive prompts to configure:
   - Container settings (ID, hostname, password)
   - Resource allocation (memory, swap, storage)
   - Network configuration (IP address, gateway)
   - Alpaca API credentials

The script will validate your inputs and provide clear feedback throughout the process.

## Configuration Options

### Container Settings
- Container ID: Unique identifier (default: 1000)
- Hostname: Container name (default: dadstocks)
- Root Password: Secure password for container access

### Resource Allocation
- Memory: Container memory limit in MB (default: 2048)
- Swap: Container swap size in MB (default: 512)
- Storage: Proxmox storage location (default: local-lvm)

### Network Configuration
- IP Address: Container IP in CIDR format (e.g., 192.168.1.100/24)
- Gateway: Network gateway IP address

### Application Settings
- Alpaca API Key: Your Alpaca API key
- Alpaca Secret Key: Your Alpaca API secret key
- Admin credentials are automatically generated and displayed after deployment

## Security Notes

1. The script automatically generates:
   - A secure random SECRET_KEY for Flask
   - A random admin password
   - Secure container configuration

2. Additional security considerations:
   - Consider setting up SSL/TLS with Let's Encrypt
   - Configure firewall rules as needed
   - Keep the system and application updated

## Maintenance

### Viewing Logs
```bash
# Application logs
pct exec <CT_ID> -- docker-compose -f /opt/dadstocks/docker-compose.yml logs -f

# Nginx logs
pct exec <CT_ID> -- tail -f /var/log/nginx/access.log
pct exec <CT_ID> -- tail -f /var/log/nginx/error.log
```

### Updates
```bash
# Update application
pct exec <CT_ID> -- cd /opt/dadstocks && git pull && docker-compose up -d --build

# Update system packages
pct exec <CT_ID> -- apt update && apt upgrade -y
```

### Backup
```bash
# Backup container
vzdump <CT_ID>

# Backup application data
pct exec <CT_ID> -- tar -czf /root/dadstocks-backup.tar.gz /opt/dadstocks/instance
```

## Troubleshooting

1. If the container fails to start:
   ```bash
   pct status <CT_ID>
   pct start <CT_ID>
   ```

2. If the application is not accessible:
   ```bash
   # Check if Docker containers are running
   pct exec <CT_ID> -- docker ps
   
   # Check Nginx status
   pct exec <CT_ID> -- systemctl status nginx
   ```

3. If you need to reset the application:
   ```bash
   pct exec <CT_ID> -- cd /opt/dadstocks && docker-compose down -v && docker-compose up -d
   ```

## Error Messages

The script includes comprehensive error checking and will display clear error messages if:
- The script is not run on a Proxmox host
- Container creation fails
- Package installation fails
- Docker or Docker Compose installation fails
- Repository cloning fails
- Application startup fails

## Support

For issues and support:
1. Check the application logs
2. Review the [GitHub repository](https://github.com/gmoorevt/dadstocks)
3. Submit an issue on GitHub 