.PHONY: clean lint pipup devsetup test

clean:
	rm -rf dist
	rm -rf src/jpp.egg-info

lint:
	pre-commit run -a

.venv:
	python -m venv .venv/jpp

pipup: .venv
	.venv/jpp/bin/pip install --upgrade pip

devsetup: .venv pipup
	.venv/jpp/bin/pip install -r requirements-dev.txt
	env pre-commit -V > /dev/null 2>&1 || .venv/jpp/bin/pip install pre-commit

test:
	tox -p all
