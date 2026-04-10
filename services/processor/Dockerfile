# In order for this Dockerfile to work it needs to be built from the `services` directory
FROM python:3.11-alpine3.18 AS builder

# Install build dependencies
RUN apk add --update --no-cache git curl build-base libffi-dev

# Download and install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Create Working directory `/service` and copy `processor`
WORKDIR /service
COPY processor/pyproject.toml /service/pyproject.toml

# Sync dependencies using uv to a virtual environment
RUN uv venv --python $(which python) && \
    uv pip install -r pyproject.toml

# Final stage
FROM python:3.11-alpine3.18
ENV PYTHONUNBUFFERED=1

# Copy the virtual environment from the builder
COPY --from=builder /service/.venv /venv
ENV PATH="/venv/bin:$PATH"

# Create Working directory `/service` and copy the code
WORKDIR /service
COPY processor/processor /service/processor
COPY shotgrid_common /service

# Create a group and user: ayonuser
RUN addgroup -S ayonuser && adduser -SH ayonuser -G ayonuser

RUN chown ayonuser:ayonuser -R /service
RUN chmod 777 -R /service

# Tell docker that all future commands should run as the appuser user
USER ayonuser

CMD ["python", "-m", "processor"]

