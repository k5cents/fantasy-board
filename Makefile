CIRCUITPY := /Volumes/CIRCUITPY
HOST      := k5aux
SSH_PORT  := 55
REMOTE    := ~/services/fantasy-board

.PHONY: help test serve board board-libs deploy logs

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "%-12s %s\n", $$1, $$2}'

test: ## Run the server unit tests
	python3 -m unittest discover -s tests

serve: ## Run the server locally on :8000
	python3 server/app.py

board: ## Copy board/ to CIRCUITPY (keeps the board's own settings.toml)
	@test -d $(CIRCUITPY) || { echo "$(CIRCUITPY) not mounted"; exit 1; }
	COPYFILE_DISABLE=1 rsync -rt \
		--exclude '._*' --exclude '.DS_Store' \
		--exclude 'settings.toml*' --exclude 'requirements.txt' \
		board/ $(CIRCUITPY)/
	-dot_clean -m $(CIRCUITPY)
	@echo "copied; the board reloads itself"

board-libs: ## Install CircuitPython libraries with circup (uv tool install circup)
	circup install -r board/requirements.txt

deploy: ## Push the server to k5aux and rebuild the container
	rsync -rt -e 'ssh -p $(SSH_PORT)' --exclude '__pycache__' server/ $(HOST):$(REMOTE)/
	ssh -p $(SSH_PORT) $(HOST) 'cd $(REMOTE) && docker compose up -d --build'
	@echo "deployed; check http://$(HOST).lan:8000/healthz"

logs: ## Tail the container log on k5aux
	ssh -p $(SSH_PORT) $(HOST) 'cd $(REMOTE) && docker compose logs -f --tail 50'
