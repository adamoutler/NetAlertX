#! /bin/bash


# Setup source directory
mkdir -p /app
rm -Rf /app/*
echo "Dev">/app/.VERSION
cp -R /workspaces/NetAlertX/CODE_OF_CONDUCT.md /app/
ln -s /workspaces/NetAlertX/api /app/api
ln -s /workspaces/NetAlertX/back /app/back
ln -s /workspaces/NetAlertX/config /app/config
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
export APP_DATA_LOCATION=/app/db
export APP_CONFIG_LOCATION=/app/config
export LOGS_LOCATION=/app/logs

TZ=Europe/Paris
PORT=20211

DEV_LOCATION=/path/to/local/source/code

/app/dockerfiles/init.sh || echo "ERROR in init.sh"

install -d -o nginx -g www-data /run/php/

APP_DIR="/app"
APP_COMMAND="python /app/server"

PHP_FPM_BIN="/usr/sbin/php-fpm83"
NGINX_BIN="/usr/sbin/nginx"
CROND_BIN="/usr/sbin/crond"

killall python &>/dev/null

# main: orchestrates PHP config and starts services + app
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
    tail -f /dev/null
}

# configure_php: configure PHP-FPM and enable dev debug options
configure_php() {
    echo "[1/2] Configuring PHP-FPM..."
    install -d -o nginx -g www-data /run/php/ &>/dev/null
    sed -i "/^;pid/c\pid = /run/php/php8.3-fpm.pid" /etc/php83/php-fpm.conf
    sed -i "/^listen/c\listen = /run/php/php8.3-fpm.sock" /etc/php83/php-fpm.d/www.conf
    sed -i "/^;listen.owner/c\listen.owner = nginx" /etc/php83/php-fpm.d/www.conf
    sed -i "/^;listen.group/c\listen.group = www-data" /etc/php83/php-fpm.d/www.conf
    sed -i "/^user/c\user = nginx" /etc/php83/php-fpm.d/www.conf

    mkdir -p /etc/php83/conf.d
    cat > /etc/php83/conf.d/99-debug.ini <<'PHPINI'
display_errors=1
display_startup_errors=1
log_errors=1
error_reporting=E_ALL
error_log=/var/log/php/php_errors.log
PHPINI
    mkdir -p /var/log/php
    touch /var/log/php/php_errors.log
    chown -R nginx:www-data /var/log/php
    chmod 660 /var/log/php/php_errors.log

    cat > /etc/php83/conf.d/99-xdebug.ini <<'XDEBUG'
zend_extension="xdebug.so"
[xdebug]
xdebug.mode=develop,debug
xdebug.log_level=0
xdebug.client_host=host.docker.internal
xdebug.client_port=9003
xdebug.start_with_request=yes
xdebug.discover_client_host=1
XDEBUG

    if [[ "${ENABLE_DEBUG:-0}" == "1" ]]; then
        APP_COMMAND="python -m debugpy --listen 0.0.0.0:5678 --wait-for-client /app/server"
    else
        APP_COMMAND="python /app/server"
    fi

}

# start_services: start crond, PHP-FPM, nginx and the application
start_services() {
    echo "[2/2] Starting services..."

    killall crond &>/dev/null
    $CROND_BIN -f &

    killall php-fpm83 &>/dev/null
    $PHP_FPM_BIN -F &

    killall nginx &>/dev/null
    envsubst '$LISTEN_ADDR $PORT $INSTALL_DIR' < /workspaces/NetAlertX/install/netalertx.template.conf > /etc/nginx/http.d/netalertx-frontend.conf
    $NGINX_BIN  &

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



