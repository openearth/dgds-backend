from setuptools import setup, find_packages

setup(
    name='dgds_backend',
    version='1.0',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'jinja2',
        'flask-caching',
        'flask-apispec',
        'apispec>=2,<3',
        'marshmallow',
        'flask_cors',
        'requests',
        'flask'
    ],
)
