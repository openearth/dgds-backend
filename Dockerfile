FROM tiangolo/uwsgi-nginx-flask:python3.8

# make system up to date
RUN apt-get -y update && apt-get -y upgrade

# set uwsgi file location
ENV UWSGI_INI /app/dgds_backend/uwsgi.ini

# add app under default location
COPY . /app

# install
RUN pip install -e /app

WORKDIR /app/dgds_backend


