from setuptools import setup

setup(
    name="ksconf-jinja-markdown",
    version="1.2.0",
    install_requires=[
        "commonmark>=0.9",
        "jinja2>=3.0",
        "ksconf>=0.13.0",
    ],
    entry_points={
        "ksconf_plugin": [
            "jinja-markdown = ksconf.plugins.jinja_markdown"
        ]
    },
    packages=["ksconf.plugins"],
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
    zip_safe=False
)
