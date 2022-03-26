from setuptools import setup

from setup import get_ver

setup(name="kintyre-splunk-conf",
      version=get_ver(),
      description="KSCONF: Ksconf Splunk Configuration Tool",
      long_description=""
      "Starting in v0.10, this package has moved to `ksconf`. "
      "Earlier version of this package supports Python 2.7 & Python 3.6 "
      "For all other use cases, visit https://pypi.org/project/ksconf/",
      keywords='ksconf splunk kinytre conf tool',
      author="Lowell Alleman",
      author_email="lowell@kintyre.co",
      url="https://github.com/Kintyre/ksconf",
      install_requires=[
          f"ksconf=={get_ver()}",
      ],
      include_package_data=True,
      zip_safe=True
      )
