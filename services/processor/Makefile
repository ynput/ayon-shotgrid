image := ynput/ayon-shotgrid-processor:0.0.1

build:
	podman build -t $(image) --no-cache . 

clean:
	if podman images | grep $(image); then \
		podman rmi $(image); \
	fi

clean-build: clean build

dev:
	podman run --rm -u ayonuser -ti \
		-v $(CURDIR):/service:Z \
		--env AYON_TOKEN="e830b1c303e04fa8a0e9d84015cab030" \
		--env AYON_SERVER_URL="http://0.0.0.0:5000" \
		--env AY_ADDON_NAME=shotgrid \
		--env AY_ADDON_VERSION=0.0.1 \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(image) python -m processor



shell:
	podman run --rm -u ayonuser -ti -v $(CURDIR):/service:Z $(image) /bin/sh
