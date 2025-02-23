# Proxmox Deployment Guide

This guide explains how to deploy Dad's Stocks Dashboard in a production environment using Proxmox VE.

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

2. Edit the configuration variables in `setup.sh`:
   - `CT_ID`: Unique container ID
   - `CT_HOSTNAME`: Container hostname
   - `CT_PASSWORD`: Secure container root password
   - `CT_NETWORK_IP`: Container IP address
   - `CT_NETWORK_GW`: Network gateway

3. Run the script on your Proxmox host:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

4. After deployment, update the Alpaca API credentials:
   ```bash
   pct exec <CT_ID> -- nano /opt/dadstocks/.env
   ```

## Configuration Options

### Memory and Storage
- `CT_MEMORY`: Container memory limit (default: 2GB)
- `CT_SWAP`: Container swap size (default: 512MB)
- `CT_STORAGE`: Proxmox storage location (default: local-lvm)

### Network
- Container uses DHCP by default
- Nginx configured to listen on port 80
- Application runs on port 5001 internally

## Security Notes

1. Change the default admin password in `.env`
2. Consider setting up SSL/TLS with Let's Encrypt
3. Configure firewall rules as needed
4. Keep the system and application updated

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

## Support

For issues and support:
1. Check the application logs
2. Review the [GitHub repository](https://github.com/gmoorevt/dadstocks)
3. Submit an issue on GitHub 