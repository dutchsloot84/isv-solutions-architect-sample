.PHONY: test lint docker

lint:
	pre-commit run --all-files

test:
	pytest services/partner-app/tests
	npm test --prefix services/integration-hub
	npm test --prefix services/salesforce-mock

docker:
	docker compose build
