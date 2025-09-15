#! /bin/bash
rm -Rf /app/*
echo "Dev">/app/.VERSION
cp -R /workspaces/NetAlertX/CODE_OF_CONDUCT.md /app/
ln -s /workspaces/NetAlertX/api /app/api
ln -s /workspaces/NetAlertX/back /app/back
ln -s /workspaces/NetAlertX/config /app/config
ln -s /workspaces/NetAlertX/db /app/db
cp -R /workspaces/NetAlertX/dockerfiles /app/dockerfiles
ln -s /workspaces/NetAlertX/front /app/front
ln -s /workspaces/NetAlertX/install /app/install
ln -s /workspaces/NetAlertX/log /app/log
ln -s /workspaces/NetAlertX/mkdocs.yml /app/mkdocs.yml
ln -s /workspaces/NetAlertX/scripts /app/scripts
ln -s /workspaces/NetAlertX/server /app/server
ln -s /workspaces/NetAlertX/test /app/test
export ALWAYS_FRESH_INSTALL=false
export INSTALL_DIR=/app


/app/dockerfiles/init.sh || echo "ERROR in init.sh"

# Create directory and set permissions
install -d -o nginx -g www-data /run/php/
#!/bin/bash
# A script to manually start dev services in a container.

# --- User Configuration ---
# IMPORTANT: Change this to the absolute path of your application's root directory.
APP_DIR="/app"

# Command to run your application. Assumes it's a python script in the APP_DIR.
APP_COMMAND="python /app/server"
# --------------------------

# --- Service Paths (change if non-standard) ---
PHP_FPM_BIN="/usr/sbin/php-fpm83"
NGINX_BIN="/usr/sbin/nginx"
CROND_BIN="/usr/sbin/crond"

#kill all python
killall python &>/dev/null

main() {
    echo "--- Starting Development Services ---"

    configure_php
    start_services

    echo
    echo "--- All services are running in the background. ---"
    echo "Processes:"
    ps -ef | grep -E 'nginx|php-fpm|crond|python'
    echo
    echo "Container is alive. Press Ctrl+C to stop."
    
    # Keep the script running to prevent the container from exiting.
    tail -f /dev/null
}

configure_php() {
    echo "[1/2] Configuring PHP-FPM..."
    install -d -o nginx -g www-data /run/php/ &>/dev/null
    sed -i "/^;pid/c\pid = /run/php/php8.3-fpm.pid" /etc/php83/php-fpm.conf
    sed -i "/^listen/c\listen = /run/php/php8.3-fpm.sock" /etc/php83/php-fpm.d/www.conf
    sed -i "/^;listen.owner/c\listen.owner = nginx" /etc/php83/php-fpm.d/www.conf
    sed -i "/^;listen.group/c\listen.group = www-data" /etc/php83/php-fpm.d/www.conf
    sed -i "/^user/c\user = nginx" /etc/php83/php-fpm.d/www.conf
    sed -i "/^group/c\group = www-data" /etc/php83/php-fpm.d/www.conf
}

start_services() {
    echo "[2/2] Starting services..."

    # Start system services
    echo "      -> Cleaning up old crond instances..."
    killall crond &>/dev/null
    echo "      -> Starting crond..."
    $CROND_BIN -f &

    echo "      -> Cleaning up old PHP-FPM instances..."
    killall php-fpm83 &>/dev/null
    echo "      -> Starting PHP-FPM..."
    $PHP_FPM_BIN -F &

    echo "      -> Cleaning up old Nginx instances..."
    killall nginx &>/dev/null
    echo "      -> Starting Nginx..."
    $NGINX_BIN -g 'daemon off;' &

    # Navigate to app directory and start the application
    if [[ -d "$APP_DIR" ]]; then
        echo "      -> Starting Application in ${APP_DIR}..."
        cd "$APP_DIR"
        $APP_COMMAND &
    else
        echo "[WARNING] Application directory '${APP_DIR}' not found. Skipping app start."
    fi
}


date +%s > /app/front/buildtimestamp.txt

echo "$(git rev-parse --short=8 HEAD)">/app/.VERSION
# Run the main function
main



