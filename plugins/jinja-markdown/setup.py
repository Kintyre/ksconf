from setuptools import setup

# TODO: Figure out if there's a way to move this into a virtual ksconf.plugins.* namespace
#       (owned by multiple packages) need to re-work namespace support in the
#       main ksconf package first.  Legacy issues caused because ksconf/__init__.py
#       exists and has already be deployed....

setup(
    name="ksconf-jinja-markdown",
    version="0.9.0",
    install_requires=[
        "commonmark>=0.9",
        "jinja2>=3.0",
        "ksconf>=0.11.6",
    ],
    entry_points={
        "ksconf_plugin": [
            "jinja-markdown = ksconf_jinja_markdown"]
    },
    py_modules=["ksconf_jinja_markdown"],
    description="Markdown rendering support for Jinja2 templates within Ksconf",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Environment :: Plugins",
        "Topic :: Text Processing :: Markup",
        "Programming Language :: Python :: 3",
    ],
    keywords='ksconf splunk jinja markdown',
    author="Lowell Alleman",
    author_email="lowell.alleman@cdillc.com",
    url="https://github.com/Kintyre/ksconf/tree/devel/plugins/jinja-markdown",
    zip_safe=True,
)
