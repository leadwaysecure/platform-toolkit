.PHONY: setup lint test check image

setup:
	cd python && pip install -e '.[dev]'

lint:
	shellcheck bash/*.sh
	cd python && ruff check src tests

test:
	bash bash/onboard-team.sh -t make-test -g make-group --dry-run > /dev/null
	cd python && pytest -q

check: lint test

image:
	podman build -t quay.io/YOUR_ORG/platform-toolkit:0.1.0 -f Containerfile .
