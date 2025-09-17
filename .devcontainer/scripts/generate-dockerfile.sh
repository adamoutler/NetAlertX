#!/bin/sh


# Make a copy of the original Dockerfile to the .devcontainer folder 
# but remove the COPY . ${INSTALL_DIR}/ command from it. This is done
# to avoid overwriting the /app directory in the devcontainer with a copy
# of the source code from the host, which would break the symlinks and 
# debugging capabilities.
sed '/${INSTALL_DIR}/d' /workspaces/NetAlertX/Dockerfile > /workspaces/NetAlertX/.devcontainer/Dockerfile


# sed the line https://github.com/foreign-sub/aiofreepybox.git \ to remove trailing backslash
sed -i '/aiofreepybox.git/ s/ \\$//' /workspaces/NetAlertX/.devcontainer/Dockerfile


# don't cat the file, just copy it in because it doesn't exist at build time
sed -i 's|^ RUN cat ${INSTALL_DIR}/install/freebox_certificate.pem >> /opt/venv/lib/python3.12/site-packages/aiofreepybox/freebox_certificates.pem$| COPY install/freebox_certificate.pem /opt/venv/lib/python3.12/site-packages/aiofreepybox/freebox_certificates.pem |' /workspaces/NetAlertX/.devcontainer/Dockerfile

cat /workspaces/NetAlertX/.devcontainer/resources/devcontainer-Dockerfile >> /workspaces/NetAlertX/.devcontainer/Dockerfile
