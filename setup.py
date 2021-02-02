from setuptools import setup, find_packages

setup(
    name='dgds_backend',
    version='1.0',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Flask==1.1.*",
        "Flask-Cors==3.0.*",
        "requests==2.23.*",
        "Flask-Caching==1.9.*",
        "Jinja2==2.11.*",
        "apispec==2.0.*",
        "flask-apispec==0.9.*",
        "google-api-core==1.21.*",
        "google-auth==1.18.*",
        "google-cloud-core==1.3.*",
        "google-cloud-storage==1.29.*",
        "googleapis-common-protos==1.52.*",
        "google-resumable-media==0.5.*",
        "marshmallow==3.6.*",
        "webargs==5.5.*",
    ],
)
