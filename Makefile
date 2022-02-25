all: run

clean:
	rm -rf venv && rm -rf *.egg-info && rm -rf dist && rm -rf *.log*

venv:
	virtualenv --python=python3.8 venv && venv/bin/python setup.py develop

run: venv
	FLASK_APP=dgds_backend.app DGDS_BACKEND_SETTINGS=../settings.cfg venv/bin/flask run

test: venv
	DGDS_BACKEND_SETTINGS=../settings.cfg venv/bin/coverage run -m unittest discover -s tests

sdist: venv
	venv/bin/python setup.py sdist
