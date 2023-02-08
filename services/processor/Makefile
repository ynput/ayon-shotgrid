image := ynput/ayon-shotgrid-processor:0.0.1

build:
	docker build -t $(image) . 

clean:
	if docker images | grep $(image); then \
		docker rmi $(image); \
	fi

clean-build: clean build

dev:
	docker run --rm -u ayonuser -ti \
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
	docker run --rm -u ayonuser -ti -v $(CURDIR):/service:Z $(image) /bin/sh
