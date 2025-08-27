#!/bin/bash

# It takes some time for outbound internet access to start working via the NAT router. Wait for this with a retry script.
for i in {1..10}; do
    if curl -s https://www.google.com --max-time 5 > /dev/null; then
        echo "Outbound access is working!"
        break
    else
        echo "Waiting for NAT to be ready..."
        sleep 5
    fi
done

# Redirect all the following output to /install.log
exec > /tmp/install.log 2>&1
chmod 777 /tmp/install.log

# Update and install system packages
apt-get update
apt-get install -y apt-transport-https ca-certificates curl software-properties-common members vim python3-pandas

# Install Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    add-apt-repository \
        "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) \
        stable"
apt-get update
apt-get install -y docker-ce

# Install Nginx
apt-get install -y nginx
cat > /etc/nginx/sites-available/coder << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";           
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/coder /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Start nginx
systemctl reload nginx
systemctl enable nginx

# Install Coder
export HOME=/root
curl -L https://coder.com/install.sh | sh
systemctl enable --now coder
journalctl -u coder.service -b

# Since Coder is running as a systemd service, we need to set environment variables in the coder.service.d directory
mkdir -p /etc/systemd/system/coder.service.d
echo -e "[Service]\n\
Environment=CODER_ACCESS_URL=https://platform.vectorinstitute.ai\n\
Environment=CODER_WILDCARD_ACCESS_URL=*.platform.vectorinstitute.ai\n\
Environment=CODER_OAUTH2_GITHUB_ALLOW_SIGNUPS=true\n\
Environment=CODER_OAUTH2_GITHUB_ALLOWED_ORGS=<GH_ALLOWED_ORGS>\n\
Environment=CODER_OAUTH2_GITHUB_CLIENT_ID=<GH_OAUTH_CLIENT_ID>\n\
Environment=CODER_OAUTH2_GITHUB_CLIENT_SECRET=<GH_OAUTH_CLIENT_SECRET>\n\
Environment=CODER_HTTP_ADDRESS=127.0.0.1:3000\n\
Environment=CODER_EXTERNAL_AUTH_0_ID=<GH_APP_ID>\n\
Environment=CODER_EXTERNAL_AUTH_0_TYPE=github\n\
Environment=CODER_EXTERNAL_AUTH_0_CLIENT_ID=<GH_APP_CLIENT_ID>\n\
Environment=CODER_EXTERNAL_AUTH_0_CLIENT_SECRET=<GH_APP_CLIENT_SECRET>\n\
Environment=CODER_EXTERNAL_AUTH_0_SCOPES=repo,workflow,admin:public_key\n\
Environment=CODER_LOG_LEVEL=debug" > /etc/systemd/system/coder.service.d/override.conf

# Reload systemd to apply the changes
systemctl daemon-reload

# Restart the Coder service to apply the new environment variables
systemctl restart coder
