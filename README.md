# dgds_backend

dgds_backend description

## Quick Start

Run the application:

    make run

And open it in the browser at [http://127.0.0.1:5000/](http://127.0.0.1:5000/)


## Prerequisites

This is built to be used with Python 3.

Some Flask dependencies are compiled during installation, so `gcc` and Python header files need to be present.
For example, on Ubuntu:

    apt install build-essential python3-dev


## Development environment - Linux

 - create virtualenv with Flask and dgds_backend installed into it (latter is installed in
   [develop mode](http://setuptools.readthedocs.io/en/latest/setuptools.html#development-mode) which allows
   modifying source code directly without a need to re-install the app): `make venv`

 - run development server in debug mode: `make run`; Flask will restart if source code is modified

 - View the app API: navigate to [http://127.0.0.1:5000/apidocs](http://127.0.0.1:5000/apidocs)

 - run tests: `make test` (see also: [Testing Flask Applications](http://flask.pocoo.org/docs/0.12/testing/))

 - create source distribution: `make sdist` (will run tests first)

 - to remove virtualenv and built distributions: `make clean`

## Development environment - Windows

 - Set environment variable: `set FLASK_APP=dgds_backend`

 - Set environment variable: `set DGDS_BACKEND_SETTINGS=../settings.cfg`

 - Enter development mode: `python setup.py develop`

 - Run the app: `python dgds_backend\app.py`

 - View the app API: navigate to [http://127.0.0.1:5000/apidocs](http://127.0.0.1:5000/apidocs)

 - Test the app: `python -m unittest discover -s tests`

## Release process

 - to add more python dependencies: add to `install_requires` in `setup.py`

 - to modify configuration in development environment: edit file `settings.cfg`; this is a local configuration file
   and it is *ignored* by Git - make sure to put a proper configuration file to a production environment when
   deploying


## Deployment

If you are interested in an out-of-the-box deployment automation, check out accompanying
[`cookiecutter-flask-ansible`](https://github.com/candidtim/cookiecutter-flask-ansible).

Or, check out [Deploying with Fabric](http://flask.pocoo.org/docs/0.12/patterns/fabric/#fabric-deployment) on one of the
possible ways to automate the deployment.

In either case, generally the idea is to build a package (`make sdist`), deliver it to a server (`scp ...`),
install it (`pip install dgds_backend.tar.gz`), ensure that configuration file exists and
`DGDS_BACKEND_SETTINGS` environment variable points to it, ensure that user has access to the
working directory to create and write log files in it, and finally run a
[WSGI container](http://flask.pocoo.org/docs/0.12/deploying/wsgi-standalone/) with the application.
And, most likely, it will also run behind a
[reverse proxy](http://flask.pocoo.org/docs/0.12/deploying/wsgi-standalone/#proxy-setups).

## Deploy with ansible 

- Install Ansible (in a virtual environment) `pip install ansible`

- Add hosts file ( [develop] )

- change variables in group_vars/all

- Run ansible script `ansible-playbook site.yml -i hosts -l develop -k -K -u <sudo_user>`
