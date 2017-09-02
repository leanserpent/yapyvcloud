try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
setup(
    name = 'yapyvcloud',
    packages = ['yapyvcloud'],
    version = '0.2',
    description = 'yet another pyvcloud',
    author = 'lean.serpent',
    author_email = 'lean.serpent@gmail.com',
    url = 'https://github.com/leanserpent/yapyvcloud',
    download_url = 'https://github.com/leanserpent/yapyvcloud/archive/v0.2.tar.gz',
    keywords = ['python', 'vcloud'],
    install_requires = ['datetime','random','bs4','lxml'],
    scripts = []
)

