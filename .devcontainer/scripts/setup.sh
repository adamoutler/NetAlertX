#! /bin/bash


# Setup source directory
mkdir -p /app
rm -Rf /app/*
echo "Dev">/app/.VERSION
cp -R /workspaces/NetAlertX/CODE_OF_CONDUCT.md /app/
ln -s /workspaces/NetAlertX/api /app/api
ln -s /workspaces/NetAlertX/back /app/back
mkdir /app/config
ln -s /workspaces/NetAlertX/db /app/db
cp -R /workspaces/NetAlertX/dockerfiles /app/dockerfiles
ln -s /workspaces/NetAlertX/docs /app/docs
ln -s /workspaces/NetAlertX/front /app/front
ln -s /workspaces/NetAlertX/install /app/install
ln -s /workspaces/NetAlertX/log /app/log
ln -s /workspaces/NetAlertX/scripts /app/scripts
ln -s /workspaces/NetAlertX/server /app/server
ln -s /workspaces/NetAlertX/test /app/test
ln -s /workspaces/NetAlertX/mkdocs.yml /app/mkdocs.yml

# Define variables (paths, ports, environment)
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


TZ=Europe/Paris
PORT=20211

DEV_LOCATION=/path/to/local/source/code


#init.sh items

cp -na "${INSTALL_DIR}/back/${CONF_FILE}" "${INSTALL_DIR}/config/${CONF_FILE}"
cp -na "${INSTALL_DIR}/back/${DB_FILE}" "${FULL_FILEDB_PATH}"
chmod 777 ${INSTALL_DIR}/
chmod 777 ${INSTALL_DIR}/config
chmod 777 ${INSTALL_DIR}/config/*
touch "${INSTALL_DIR}"/log/{app.log,execution_queue.log,app_front.log,app.php_errors.log,stderr.log,stdout.log,db_is_locked.log}
touch "${INSTALL_DIR}"/api/user_notifications.json
date +%s > "${INSTALL_DIR}/front/buildtimestamp.txt"

# Ensure the config directory and file are readable by the PHP-FPM/nginx user
if [ -d "${INSTALL_DIR}/config" ]; then
    chmod 755 "${INSTALL_DIR}/config" || true
fi
if [ -f "${INSTALL_DIR}/config/${CONF_FILE}" ]; then
    chown nginx:www-data "${INSTALL_DIR}/config/${CONF_FILE}" || true
    chmod 640 "${INSTALL_DIR}/config/${CONF_FILE}" || true
fi





install -d -o nginx -g www-data /run/php/

APP_DIR="/app"
APP_COMMAND="python3 /app/server"
PHP_FPM_BIN="/usr/sbin/php-fpm83"
NGINX_BIN="/usr/sbin/nginx"
CROND_BIN="/usr/sbin/crond"



killall python &>/dev/null
sleep 1

# main: orchestrates PHP config and starts services + app
main() {
    echo "--- Starting Development Services ---"

    configure_php

    # No python wrapper installation in dev container; use python3 directly

    start_services

    echo
    echo "--- All services are running in the background. ---"
    echo "Processes:"
    ps -ef | grep -E 'nginx|php-fpm|crond|python' || true
    echo
    echo "Emitting recent startup logs for nginx, php-fpm and app (script will exit when done)."

    # Allow some time for processes to write initial logs
    sleep 0.5

    

    echo "Setup complete. Exiting setup script. Services continue running in background."
}

# Note: Removed python3 debug wrapper installation per request.
# The container will use the system python3 binary directly when launching the app.

# start_services: start crond, PHP-FPM, nginx and the application
start_services() {
    echo "[2/2] Starting services..."

    killall crond &>/dev/null || true
    $CROND_BIN -f &

    killall php-fpm83 &>/dev/null || true
    # Give the OS a moment to release the php-fpm socket
    sleep 0.3
    # Start php-fpm in foreground but redirect its stdout/stderr to a dedicated log
    mkdir -p /var/log/php
    touch /var/log/php/php-fpm.stdout.log
    chown nginx:www-data /var/log/php/php-fpm.stdout.log || true
    $PHP_FPM_BIN -F > /var/log/php/php-fpm.stdout.log 2>&1 &

    # After starting php-fpm, ensure the unix socket has the right ownership and perms
    # (sometimes php-fpm creates the socket as root; nginx needs 'nginx' user and 'www-data' group)
    sleep 0.1
    if [ -e /run/php/php8.3-fpm.sock ]; then
        chown nginx:www-data /run/php/php8.3-fpm.sock || true
        chmod 0660 /run/php/php8.3-fpm.sock || true
    fi

    killall nginx &>/dev/null || true
    # Wait for the previous nginx processes to exit and for the port to free up
    tries=0
    # Check for listeners on the port and wait up to a short timeout
    while ss -ltn | grep -q ":${PORT}[[:space:]]" && [ $tries -lt 10 ]; do
        echo "  -> Waiting for port ${PORT} to free..."
        sleep 0.2
        tries=$((tries+1))
    done
    envsubst '$LISTEN_ADDR $PORT $INSTALL_DIR' < /workspaces/NetAlertX/install/netalertx.template.conf > /etc/nginx/http.d/netalertx-frontend.conf
    # Start nginx (it manages its own log files in /var/log/nginx)
    $NGINX_BIN &

  
    echo "      -> Starting Application in ${APP_DIR}/server..."
    # Ensure app log directory exists
    mkdir -p /app/log
    touch /app/log/app_stdout.log /app/log/app_stderr.log || true
    # Start the server from the server package directory so imports like `import conf` resolve

    cd "${APP_DIR}/server"
    # Run the package entrypoint directly to set the proper module path
    # Start the app using the system python3 directly
    PYBIN="$(command -v python3 || command -v python || true)"
    echo "      -> Launching app with python binary: $PYBIN"
    if [ -n "$PYBIN" ]; then
        nohup "$PYBIN" __main__.py > /app/log/app_stdout.log 2>/app/log/app_stderr.log &
    else
        echo "  -> ERROR: No python interpreter found (python3/python). App will not start."
    fi
   
    # give it a moment to start and verify it's listening on the API port
    sleep 0.3
    if ss -ltn | grep -q ":20212[[:space:]]"; then
        echo "  -> Application started and listening on 20212"
    else
        echo "  -> Application did not appear to listen on 20212, attempting a restart..."
        # attempt a clean restart once more and capture output
        pkill -f "__main__.py" || true
        sleep 0.1
        cd "${APP_DIR}/server" || true
    nohup python3 __main__.py > /app/log/app_stdout.log 2>/app/log/app_stderr.log &
        sleep 0.5
        if ss -ltn | grep -q ":20212[[:space:]]"; then
            echo "  -> Application restart succeeded and is listening on 20212"
        else
            echo "  -> WARNING: Application still not listening on 20212 after restart. Check /app/log/app_stderr.log for errors."
        fi
    fi


}

# configure_php: configure PHP-FPM and enable dev debug options
configure_php() {
    echo "[1/2] Configuring PHP-FPM..."
    install -d -o nginx -g www-data /run/php/ &>/dev/null
    sed -i "/^;pid/c\pid = /run/php/php8.3-fpm.pid" /etc/php83/php-fpm.conf
    sed -i "/^listen/c\listen = /run/php/php8.3-fpm.sock" /etc/php83/php-fpm.d/www.conf
    # Ensure listen.owner/listen.group and listen.mode are set (some distros may not include the commented lines)
    if grep -q "^listen.owner" /etc/php83/php-fpm.d/www.conf 2>/dev/null; then
        sed -i "/^listen.owner/c\listen.owner = nginx" /etc/php83/php-fpm.d/www.conf || true
    else
        echo "listen.owner = nginx" >> /etc/php83/php-fpm.d/www.conf || true
    fi
    if grep -q "^listen.group" /etc/php83/php-fpm.d/www.conf 2>/dev/null; then
        sed -i "/^listen.group/c\listen.group = www-data" /etc/php83/php-fpm.d/www.conf || true
    else
        echo "listen.group = www-data" >> /etc/php83/php-fpm.d/www.conf || true
    fi
    if grep -q "^listen.mode" /etc/php83/php-fpm.d/www.conf 2>/dev/null; then
        sed -i "/^listen.mode/c\listen.mode = 0660" /etc/php83/php-fpm.d/www.conf || true
    else
        echo "listen.mode = 0660" >> /etc/php83/php-fpm.d/www.conf || true
    fi
    sed -i "/^user/c\user = nginx" /etc/php83/php-fpm.d/www.conf

    mkdir -p /etc/php83/conf.d
    # enable debug logging
    # cat > /etc/php83/conf.d/99-debug.ini <<'PHPINI'
    # display_errors=1
    # display_startup_errors=1
    # log_errors=1
    # error_reporting=E_ALL
    # error_log=/var/log/php/php_errors.log
    # PHPINI
    mkdir -p /var/log/php
    touch /var/log/php/php_errors.log
    chown -R nginx:www-data /var/log/php
    chmod 660 /var/log/php/php_errors.log


    cp /workspaces/NetAlertX/.devcontainer/resources/99-xdebug.ini /etc/php83/conf.d/99-xdebug.ini
    chmod 644 /etc/php83/conf.d/99-xdebug.ini || true

}

# (duplicate start_services removed)


date +%s > /app/front/buildtimestamp.txt

echo "$(git rev-parse --short=8 HEAD)">/app/.VERSION
# Run the main function
main



