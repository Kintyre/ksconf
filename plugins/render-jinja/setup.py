from setuptools import setup

setup(
    name="ksconf-render-jinja",
    version="1.0.0",
    install_requires=[
        "jinja2>=3.0",
        "ksconf>=0.13.0",
    ],
    entry_points={
        "ksconf_plugin": [
            "render-jinja = ksconf.plugins.render_jinja"
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
        "Programming Language :: Python :: 3",
    ],
    keywords='ksconf splunk jinja',
    author="Lowell Alleman",
    author_email="lowell.alleman@cdillc.com",
    url="https://github.com/Kintyre/ksconf/tree/devel/plugins/render-jinja",
    zip_safe=False
)
