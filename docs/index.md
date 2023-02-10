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

#### In Python

```python
from kghub_downloader.download_utils import download_from_yaml

download_from_yaml(yaml_file="download.yaml", output_dir="data")
```

#### Command Line

```bash
$ downloader [OPTIONS] ARGS
```
╰ Download files listed in a download.yaml file

| OPTIONS | | 
| --- | --- |
| yaml_file | A string pointing to the download.yaml file, to be parsed for things to download.<br>Defaults to `./download.yaml` |
| ignore_cache | Ignore cache and download files even if they exist [false] |
| snippet_only | Downloads only the first 5 kB of each uncompressed source, for testing and file checks |
| tags | Limit to only downloads with this tag |
| mirror | Remote storage URL to mirror download to. Supported buckets: Google Cloud Storage |


| ARGUMENTS | | 
| --- | --- |
| output_dir | A string pointing to where to write out downloaded files. |

Examples:
```bash
$ downloader --output_dir example_output --tags zfin_gene_to_phenotype example.yaml
$ downloader --output_dir example_output --mirror gs://your-bucket/desired/directory

# Note that if your YAML file is named `download.yaml`, 
# the argument can be omitted from the CLI call.
$ downloader --output_dir example_output
```
