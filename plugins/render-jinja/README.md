# ksconf-render-jinja

Add Jinja2 handler for the `ksconf package` command.

This allows `*.j2` files located within an app directory to be rendered during app packaging.
This is enabled via `--enable-handler=jinja`.

## Install

```sh
pip install -U ksconf-render-jinja
```

Installation can be validated by running:  `ksconf --version`


```sh
ksconf package --enable-handler=jinja --template_vars @inputs.conf my_app
```


## Release steps

```sh
python setup.py build
python setup.py bdist_wheel sdist
twine upload dist/ksconf_render_jinja-*any.whl dist/ksconf-render-jinja-*.tar.gz
```
