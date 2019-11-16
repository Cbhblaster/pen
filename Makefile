.PHONY: clean compile sync syncprod lint pipup devsetup

clean:
	rm -rf dist
	rm -rf src/jpp.egg-info

compile:
	pip-compile requirements.txt
	pip-compile requirements-dev.txt

sync:
	pip-sync requirements-dev.txt

syncprod:
	pip-sync requirements.txt

lint:
	pre-commit run -a

.venv:
	python -m venv .venv/jpp

pipup:
	pip install --upgrade pip

devsetup: .venv pipup
	pip install pip-tools
	pip-sync requirements-dev.txt