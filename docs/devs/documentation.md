# Working with Documentation

This documentation is automatically built and published from the contents of the [video-streamer](https://github.com/mxcube/video-streamer) repository. Each time the repository’s `main` branch is updated, documentation is regenerated.

If you want to modify this documentation, make a pull request to the repository with your suggested changes.

## Modifying the Documentation

In this project, [MkDocs](https://www.mkdocs.org/) is used to convert Markdown files into a static website. The core of the documentation is written in Markdown files, located in the `docs/` folder, while the configuration file (`mkdocs.yml`) controls how the site is built and customized.

### Key files in the Documentation Setup

- `mkdocs.yml`: This is the configuration file for MkDocs, found in the repository's root folder. It defines the structure of the documentation site, including navigation, themes, plugins, and other settings. Below you can find an example of `mkdocs.yml`:
```yaml
site_name: MXCuBE Video-Streamer Documentation
theme: readthedocs
plugins:
  - macros
nav:
  - Home: index.md
  - About: about.md
  - Installation: installation.md
  - FAQ: faq.md

```

- `docs/` : This folder contains the source Markdown files (`.md`), which make up the content of the documentation.

```
docs/
├── index.md
├── about.md
├── installation.md
├── faq.md
└── images/

```

### Adding New Content

To add new content to the documentation, create new Markdown files in the `docs/` folder. Once you add the file, update the `mkdocs.yml` navigation structure to include it. For example, if you create a `tutorial.md` file, you would add it to `mkdocs.yml`:

```yaml
nav:
  - Home: index.md
  - Tutorial: tutorial.md
```

### Working with Macros

In this project, we use the mkdocs-macros-plugin to define custom macros. You can define macros in a custom Python script (e.g., `docs_config/main.py`) and use them throughout the documentation.

For example, the following macro will include the contents of the LICENSE file:

```python
def read_file_path(path):
    with open(path, 'r') as file:
        return file.read()
```

Then, in the Markdown files, you can use this Macro like this:
```markdown
## License
{% raw %}
{{ read_file('LICENSE') }};
{% endraw %}
```

---

## Test your Changes Locally

Before submitting your changes to the repository, please make sure that they run locally. 

### Installing MkDocs

Please follow the instructions in the [Installation Guide](../installation.md), it will automatically install `mkdocs` and all the needed plugins.

### Use the Development Server

`MkDocs` has an integrated development server that will run per default on `http://localhost:8000`. To run it navigate to the folder where `mkdocs.yml` is located and run

```bash
mkdocs serve
```

### Build the Documentation

To build the static HTML files that make up your documentation, use the following command:

```bash
mkdocs build
```
This will generate a `site/` directory in the root of the project, containing the compiled HTML files. You can then upload the contents of the `site/` folder to a web server or use it for deployment.