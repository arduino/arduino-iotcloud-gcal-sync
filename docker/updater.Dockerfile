# Use the official lightweight Python image.
# https://hub.docker.com/_/python
# Pin an explicit patch release (not the floating 3.13-slim tag) so the bundled
# CPython interpreter is reproducible and image scanning can't flag an outdated
# interpreter CVE on a stale build. Bump this when a newer 3.13.x ships.
FROM python:3.13.16-slim

# Apply Debian security updates to the base image so OS-package CVEs flagged by
# image scanning (e.g. CVE-2026-48962 in perl-base, CVE-2026-5450 in libc6/
# libc-bin) are patched on every build.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "./updater.py" ]

