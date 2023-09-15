ADDON_VERSION := $(shell grep "__version__" ../version.py | cut -d' ' -f3 | tr -d '"')
IMAGE := ynput/ayon-shotgrid-$(SERVICE):$(ADDON_VERSION)
SERVICE = $(error Please specify the service to build with 'SERVICE', for example: 'make build SERVICE=leecher')

default:
	@echo ""
	@echo "Ayon Shotgrid $(ADDON_VERSION) Service Builder"
	@echo ""
	@echo "Usage: make SERVICE=[service-name] [target]"
	@echo ""
	@echo "Passing SERVICE is required for any of the targets to work, possible services:"
	@echo ""
	@echo "  leecher - Fetch Shotgrid Events into AYON."
	@echo "  processor - Process 'shotgrid.event's in AYON."
	@echo "  transmitter - Push AYON events to Shotgrid."
	@echo ""
	@echo "Targets:"
	@echo "  build        Build docker image."
	@echo "  build-all    Build docker image for 'leecher', 'procesor' and 'transmitter'."
	@echo "  clean        Remove local images."
	@echo "  clean-build  Remove local images and build without docker cache."
	@echo "  dev          Run a service locally"
	

build:
	docker build -t $(IMAGE) -f $(SERVICE)/Dockerfile .

build-all:
	$(foreach service,leecher processor transmitter, docker build -t ynput/ayon-shotgrid-$(service):$(ADDON_VERSION) -f $(service)/Dockerfile . &)

clean:
	if docker images | grep $(IMAGE); then \
		docker rmi $(IMAGE); \
	fi

clean-build: clean
	docker build --no-cache -t $(IMAGE) -f $(SERVICE)/Dockerfile .

dev:
	-ln -s $(CURDIR)/shotgrid_common/* $(CURDIR)/$(SERVICE)
	-docker run --rm -u ayonuser -ti \
		-v $(CURDIR)/shotgrid_common:$(CURDIR)/shotgrid_common:Z \
		-v $(CURDIR)/$(SERVICE):/service:Z \
		--env-file $(CURDIR)/$(SERVICE)/.env \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(IMAGE) python -m processor

	find $(CURDIR)/$(SERVICE) -type l -delete

shell:
	docker run --rm -u ayonuser -ti -v $(CURDIR)/$(SERVICE)/$(SERVICE):/service:Z $(IMAGE) /bin/sh
	
	