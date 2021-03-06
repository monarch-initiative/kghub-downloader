# KG-Hub Downloader

| [Documentation](https://monarch-initiative.github.io/kghub-downloader) |

### Overview

This is a configuration based file caching downloader with initial support for http requests & queries against elasticsearch.

### Installation

KGHub Downloader is available to install via pip:
```
pip install kghub-downloader
```

### Configure 

#### Download Configuration

The downloader requires a YAML file which contains a list of target URLs to download, and local names to save those downloads.
The format for the file is:
```yaml
---
- 
  url: "http://example.com/myawesomefile.tsv"
  local_name: myawesomefile.tsv
-
  url: "http://example.com/myokfile.json"
  local_name: myokfile.json

```

You can also include any secrets like API keys you have set as environment variables using `{VARIABLE_NAME}`, for example:  
```yaml
---
-
  url: "https://example.com/myfancyfile.json?key={YOUR_SECRET}"
  localname: myfancyfile.json
```
Note: You _MUST_ have this secret set as an environment variable, and be sure to include the {curly braces}

### Usage

Downloader can be used directly in Python or via command line

#### In Python:

```python
from kghub_downloader.download_utils import download_from_yaml

download_from_yaml(yaml_file="download.yaml", output_dir="data")
```

#### Command Line
```bash
downloader --output_dir example_output --tags zfin_gene_to_phenotype example.yaml
```
Note: If your YAML file is named `download.yaml`, the argument can be omitted from the CLI call.  
For example, `downloader --output_dir example_output` is equivalent to `downloader --output_dir example_output download.yaml`

**Command Line Arguments:**  
- `yaml_file`: List of files to download in YAML format. Defaults to "download.yaml"  
- `output_dir`: Path to output directory. Defaults to current directory  
- `ignore_cache`: Optional boolean; if True ignores already downloaded files and download again. Defaults to False  
- `tags`: Optional list of tags, limits downloads to those with matching tags
- `mirror`: Optional URL path to remote storage to backup download. Currently supports: Google Cloud Storage
  - Note: use full path to desired directory (ex. `--mirror gs://your-bucket/desired/directory`)