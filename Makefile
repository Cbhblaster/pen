.PHONY: test clean lint pipup devsetup venv-activated

test: .venv-activated
	tox -p all

clean:
	rm -rf dist
	rm -rf src/pen.egg-info

lint: .venv-activated
	isort -y
	black .
	flake8 --exit-zero
	mypy src/pen tests

venv:
	python -m venv .venv/pen

.venv-activated:
ifndef VIRTUAL_ENV
	$(error venv not activated)
endif

pipup: .venv-activated
	.venv/pen/bin/pip install --upgrade pip

devsetup: .venv-activated pipup
	.venv/pen/bin/pip install -r requirements-dev.txt
	env pre-commit -V > /dev/null 2>&1 || .venv/pen/bin/pip install pre-commit

