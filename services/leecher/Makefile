image := ynput/ayon-shotgrid-leecher:0.0.1

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
		--env AYON_TOKEN="d39193e7dd17c18087298d499d21af0e3be5105f6f925b0cf8ae3f8f923bf27c" \
		--env AYON_SERVER_URL="http://0.0.0.0:5000" \
		--env AY_ADDON_NAME=shotgrid \
		--env AY_ADDON_VERSION=0.0.1 \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(image) python -m leecher



shell:
	podman run --rm -u ayonuser -ti -v $(CURDIR):/service:Z $(image) /bin/sh
