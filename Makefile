.PHONY: test clean lint pipup devsetup venv-activated

test: .venv-activated
	tox -p all

clean:
	rm -rf dist
	rm -rf src/jpp.egg-info

lint: .venv-activated
	isort -y
	black .
	flake8 --exit-zero
	mypy src/jpp tests

venv:
	python -m venv .venv/jpp

.venv-activated:
ifndef VIRTUAL_ENV
	$(error venv not activated)
endif

pipup: .venv-activated
	.venv/jpp/bin/pip install --upgrade pip

devsetup: .venv-activated pipup
	.venv/jpp/bin/pip install -r requirements-dev.txt
	env pre-commit -V > /dev/null 2>&1 || .venv/jpp/bin/pip install pre-commit

