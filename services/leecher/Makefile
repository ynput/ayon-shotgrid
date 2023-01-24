image := ynput/ayon-shotgrid-leecher:0.0.1

build:
	podman build -t $(image)  . 

clean:
	if podman images | grep $(image); then \
		podman rmi $(image); \
	fi

dev:
	podman run --rm -u ayonuser -ti \
		-v $(CURDIR):/service:Z \
		--env AY_API_KEY=verysecureapikey \
		--env AY_SERVER_URL="http://172.18.0.1:5000" \
		--env AY_ADDON_NAME=ftrack \
		--env AY_ADDON_VERSION=1.0.0 \
		$(image) python -m leecher


shell:
	podman run --rm -u ayonuser -ti -v $(CURDIR):/service:Z $(image) /bin/sh
