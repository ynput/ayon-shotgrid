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
		--env-file .env \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		--network=host \
		$(image) python -m processor



shell:
	docker run --rm -u ayonuser -ti -v $(CURDIR):/service:Z $(image) /bin/sh
