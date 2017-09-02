try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup
config = {
	'name': 'yapyvcloud'
	'packages': ['yapyvcloud'],
	'version': '0.1',
	'description': 'yet another pyvcloud',
	'author': 'lean.serpent',
	'author_email': 'lean.serpent@gmail.com',
	'url': 'Project Site',
	'download_url': 'Download Url',
    'keywords': ['python', 'vcloud']
	'install_requires': ['nose'],
	'scripts': [],
}

setup(**config)

