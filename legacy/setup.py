from setuptools import setup

from ksconf import __version__

setup(
    name="kintyre-splunk-conf",
    version=__version__,
    description="KSCONF: Ksconf Splunk Configuration Tool",
    long_description=""
    "Starting in v0.10, this package has moved to `ksconf`. "
    "Earlier version of this package supports Python 2.7 & Python 3.6 "
    "For all other use cases, visit https://pypi.org/project/ksconf/",
    keywords='ksconf splunk kinytre conf tool',
    author="Lowell Alleman",
    author_email="lowell@kintyre.co",
    url="https://github.com/Kintyre/ksconf",
    setup_requires=[
        "wheel",
    ],
    install_requires=[f"ksconf=={__version__}"],
    include_package_data=True,
    zip_safe=True
)
