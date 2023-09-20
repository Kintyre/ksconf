# ksconf-jinja-markdown

Add Markdown rendering support to the Ksconf packing ecosystem.
This allows rendering markdown into html when using Jinja (`*.j2`) files within
a rendered Splunk app using the `ksconf package` command.

## Jinja filter

* `markdown2html` - Filter used to convert markdown text into HTML output.

## Install

```sh
pip install -U ksconf-jinja2-markdown
```

Installation can be validated by running:  `ksconf --version`


## Example Usage

Simple XML with an input

Contents of `my_app/default/data/view/my_dashboard.xml.j2`:

```xml
<dashboard>
   <row>
      <html>
         {{ description | markdown2html }}
      </html>
   </row>
</dashboard>
```

Contents of `inputs.json`:

```json
{
    "description": "# Title\n## Header 2\n* bulleted\n* list\n"
}
```

```sh
ksconf package --enable-handler=jinja --template_vars @inputs.conf my_app
```


## Release steps

```sh
python setup.py bdist_wheel sdist
twine upload dist/ksconf_jinja_markdown-*any.whl dist/ksconf-jinja-markdown-*.tar.gz
```