ifneq (,$(wildcard ./.env))
		include .env
		export
endif

VERSION=$(shell python -c "import os;import sys;content={};f=open('$(CURDIR)/../package.py');exec(f.read(),content);f.close();print(content['version'])")

define HELP_INFO

*************************
AYON shotgrid services tool
	 Run shotgrid services
*************************

Run service processes from terminal. It is recommended to use docker images for production.

Usage: make [target]

Optional arguments for service targets:
--variant [variant] (Define settings variant. default: 'production')

Runtime targets:
	createenv    Install requirements to currently active python (recommended to create venv)
	leecher      Start leecher of shotgrid events
	processor    Main processing logic
	transmitter  Transmit AYON events to shotgrid
	services     Start all services leecher, processor and transmitter

endef
export HELP_INFO

help:
	@echo "$$HELP_INFO"

createenv:
		$(shell [[ -d $(CURDIR)/venv ]] || python -m venv $(CURDIR)/venv) && \
		. $(CURDIR)/venv/bin/activate && python -m pip install -e "$(CURDIR)"

leecher:
		export AYON_ADDON_NAME="shotgrid" && \
		export AYON_ADDON_VERSION=$(VERSION) && \
		. $(CURDIR)/venv/bin/activate && \
		python "$(CURDIR)/main.py" --service leecher $@

processor:
		export AYON_ADDON_NAME="shotgrid" && \
		export AYON_ADDON_VERSION=$(VERSION) && \
		. $(CURDIR)/venv/bin/activate && \
		python "$(CURDIR)/main.py" --service processor $@

transmitter:
		export AYON_ADDON_NAME="shotgrid" && \
		export AYON_ADDON_VERSION=$(VERSION) && \
		. $(CURDIR)/venv/bin/activate && \
		python "$(CURDIR)/main.py" --service transmitter $@

services:
		export AYON_ADDON_NAME="shotgrid" && \
		export AYON_ADDON_VERSION=$(VERSION) && \
		. $(CURDIR)/venv/bin/activate && \
		python "$(CURDIR)/main.py" --service all $@

info: help
default: help
