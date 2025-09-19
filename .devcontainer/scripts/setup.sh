#! /bin/bash
id

# Define variables (paths, ports, environment)

export APP_DIR="/app"
export APP_COMMAND="setsid  python3 /app/server"
export PHP_FPM_BIN="setsid /usr/sbin/php-fpm83"
export NGINX_BIN="setsid  /usr/sbin/nginx"
export CROND_BIN="setsid  /usr/sbin/crond"
export ALWAYS_FRESH_INSTALL=false
export INSTALL_DIR=/app
export APP_DATA_LOCATION=/app/config
export APP_CONFIG_LOCATION=/app/config
export LOGS_LOCATION=/app/logs
export CONF_FILE="app.conf"
export NGINX_CONF_FILE=netalertx.conf
export DB_FILE="app.db"
export FULL_FILEDB_PATH="${INSTALL_DIR}/db/${DB_FILE}"
export NGINX_CONFIG_FILE="/etc/nginx/http.d/${NGINX_CONF_FILE}"
export OUI_FILE="/usr/share/arp-scan/ieee-oui.txt" # Define the path to ieee-oui.txt and ieee-iab.txt
export TZ=Europe/Paris
export PORT=20211
export SOURCE_DIR="/workspaces/NetAlertX"

# Setup source directory
echo "Dev">${INSTALL_DIR}/.VERSION
cp -R ${SOURCE_DIR}/CODE_OF_CONDUCT.md ${INSTALL_DIR}/
ln -s ${SOURCE_DIR}/api ${INSTALL_DIR}/api
ln -s ${SOURCE_DIR}/back ${INSTALL_DIR}/back
cp -R ${SOURCE_DIR}/config ${INSTALL_DIR}/config
ln -s ${SOURCE_DIR}/db ${INSTALL_DIR}/db
cp -R ${SOURCE_DIR}/dockerfiles ${INSTALL_DIR}/dockerfiles
ln -s ${SOURCE_DIR}/docs ${INSTALL_DIR}/docs
ln -s ${SOURCE_DIR}/front ${INSTALL_DIR}/front
ln -s ${SOURCE_DIR}/install ${INSTALL_DIR}/install
ln -s ${SOURCE_DIR}/log ${INSTALL_DIR}/log
ln -s ${SOURCE_DIR}/scripts ${INSTALL_DIR}/scripts
ln -s ${SOURCE_DIR}/server ${INSTALL_DIR}/server
ln -s ${SOURCE_DIR}/test ${INSTALL_DIR}/test
ln -s ${SOURCE_DIR}/mkdocs.yml ${INSTALL_DIR}/mkdocs.yml

sudo find ${INSTALL_DIR}/ -type d -exec chmod 775 {} \;
sudo find ${INSTALL_DIR}/ -type f -exec chmod 664 {} \;
sudo cp -na "${INSTALL_DIR}/back/${CONF_FILE}" "${INSTALL_DIR}/config/${CONF_FILE}"
sudo cp -na "${INSTALL_DIR}/back/${DB_FILE}" "${FULL_FILEDB_PATH}"
sudo touch "${INSTALL_DIR}"/log/{app.log,execution_queue.log,app_front.log,app.php_errors.log,stderr.log,stdout.log,db_is_locked.log}
sudo touch "${INSTALL_DIR}"/api/user_notifications.json
sudo date +%s > "${INSTALL_DIR}/front/buildtimestamp.txt"
sudo chown netalertx:www-data "${INSTALL_DIR}/config/${CONF_FILE}" || true
sudo chmod 640 "${INSTALL_DIR}/config/${CONF_FILE}" || true





killall python &>/dev/null
sleep 1

# main: orchestrates PHP config and starts services + app
main() {
    echo "--- Starting Development Services ---"

    configure_php

    # No python wrapper installation in dev container; use python3 directly

    start_services

    echo
    echo "Setup complete. Exiting setup script. Services continue running in background."
}

# Note: Removed python3 debug wrapper installation per request.
# The container will use the system python3 binary directly when launching the app.

# start_services: start crond, PHP-FPM, nginx and the application
start_services() {
    echo "[2/2] Starting services..."
    killall php-fpm83 &>/dev/null || true
    killall crond &>/dev/null || true
    # Give the OS a moment to release the php-fpm socket
    sleep 0.3
    echo "      -> Starting CronD"
    $CROND_BIN -f &

    # Start php-fpm in foreground but redirect its stdout/stderr to a dedicated log

    
    
    echo "      -> Starting PHP-FPM"
    $PHP_FPM_BIN -F 2>&1 > /var/log/php/php-fpm.stdout.log &

    # After starting php-fpm, ensure the unix socket has the right ownership and perms
    # (sometimes php-fpm creates the socket as root; nginx needs 'nginx' user and 'www-data' group)
    sleep 0.1


    sudo killall nginx &>/dev/null || true
    # Wait for the previous nginx processes to exit and for the port to free up
    tries=0
    # Check for listeners on the port and wait up to a short timeout
    while ss -ltn | grep -q ":${PORT}[[:space:]]" && [ $tries -lt 10 ]; do
        echo "  -> Waiting for port ${PORT} to free..."
        sleep 0.2
        tries=$((tries+1))
    done
    sleep 0.2
    sudo rm /var/lib/nginx/logs/* 2>/dev/null || true
    # Start nginx (it manages its own log files in /var/log/nginx)
    echo "      -> Starting Nginx"
    $NGINX_BIN &

  
    echo "      -> Starting GraphQL ${APP_DIR}/server..."
    # Ensure app log directory exists
    mkdir -p /app/log
    
    touch /app/log/app_stdout.log /app/log/app_stderr.log || true
    # Start the server from the server package directory so imports like `import conf` resolve

    /workspaces/NetAlertX/.devcontainer/scripts/restart-backend.sh
    # Run the package entrypoint directly to set the proper module path
    # Start the app using the system python3 directly
    
   
   


}

# configure_php: configure PHP-FPM and enable dev debug options
configure_php() {
    echo "[1/2] Configuring PHP-FPM..."
    sudo killall php-fpm83 &>/dev/null || true
    install -d -o nginx -g www-data /run/php/ &>/dev/null
    sudo sed -i "/^;pid/c\pid = /run/php/php8.3-fpm.pid" /etc/php83/php-fpm.conf

    sudo sed -i 's|^listen = .*|listen = 127.0.0.1:9000|' /etc/php83/php-fpm.d/www.conf
    # Optional: ensure Nginx fastcgi_pass matches (adjust path/pattern if different)
    sudo sed -i 's|fastcgi_pass .*|fastcgi_pass 127.0.0.1:9000;|' /etc/nginx/http.d/*.conf

    sudo mkdir -p /etc/php83/conf.d
    sudo cp /workspaces/NetAlertX/.devcontainer/resources/99-xdebug.ini /etc/php83/conf.d/99-xdebug.ini

    # enable debug logging
    # cat > /etc/php83/conf.d/99-debug.ini <<'PHPINI'
    # display_errors=1
    # display_startup_errors=1
    # log_errors=1
    # error_reporting=E_ALL
    # error_log=/var/log/php/php_errors.log
    # PHPINI
    
    sudo rm -R /var/log/php83 &>/dev/null || true
    install -d -o netalertx -g www-data -m 755 var/log/php83;
    sudo ln -s /var/log/php /var/log/php83 || true

    sudo chmod 644 /etc/php83/conf.d/99-xdebug.ini || true

}

# (duplicate start_services removed)


date +%s > /app/front/buildtimestamp.txt

echo "$(git rev-parse --short=8 HEAD)">/app/.VERSION
# Run the main function
main



