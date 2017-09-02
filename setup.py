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
    'url': 'https://github.com/leanserpent/yapyvcloud',
    'download_url': 'https://github.com/leanserpent/yapyvcloud/archive/v0.1.tar.gz',
    'keywords': ['python', 'vcloud']
    'install_requires': ['nose'],
    'scripts': [],
}

setup(**config)

