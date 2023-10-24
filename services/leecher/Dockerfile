# In order for this Dockerfile to work it needs to be built from the `services` directory
FROM python:alpine3.16
ENV PYTHONUNBUFFERED=1
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# Install python/pip
RUN apk add --update --no-cache git curl build-base libffi-dev
RUN pip install --no-cache --upgrade pip
RUN pip install --no-cache setuptools poetry pip-autoremove

# Create Working directory `/service` and copy `leecher`
RUN mkdir /service
COPY leecher/pyproject.toml /service/pyproject.toml
WORKDIR /service

# Install dependencies with poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --only main

# Remove unnecessary packages to make the image smaller
RUN apk del git curl build-base libffi-dev
RUN python -m pip cache purge
RUN pip-autoremove -y setuptools poetry
RUN python -m pip uninstall -y pip pip-autoremove

# Create a group and user: ayonuser
RUN addgroup -S ayonuser && adduser -SH ayonuser -G ayonuser

COPY leecher/leecher /service/leecher
COPY shotgrid_common /service

RUN chown ayonuser:ayonuser -R /service

# Tell docker that all future commands should run as the appuser user
USER ayonuser

CMD ["python", "-m", "leecher"]
