FROM python:alpine3.17
ENV PYTHONUNBUFFERED=1

# Install python/pip
RUN apk add --update --no-cache python3 git curl build-base libffi-dev && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools poetry && ln -sf pip3 /usr/bin/pip

RUN mkdir /service
COPY pyproject.toml /service/pyproject.toml
WORKDIR /service
RUN cat pyproject.toml


RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi

# Create a group and user: ayonuser
RUN addgroup -S ayonuser && adduser -SH ayonuser -G ayonuser

RUN chown ayonuser:ayonuser -R /service
RUN chmod 777 -R /service

# Tell docker that all future commands should run as the appuser user
USER ayonuser

