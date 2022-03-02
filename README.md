# KG-Hub Downloader

#### Overview

This is a configuration based file caching downloader with initial support for http requests & queries against elasticsearch.

#### Installation

KGHub Downloader is available to install via pip:
```
pip install kghub-downloader
```

#### Usage

The downloader requires a YAML file which contains a list of target URLs to download, and local names to save those downloads.
The format for the file is:
```
---
- 
  url: "http://example.com/myawesomefile.tsv"
  local_name: myawesomefile.tsv
-
  url: "http://example.com/myokfile.json"
  local_name: myokfile.json

```

Downloader can be used directly in Python or via command line. 

In Python:

```
from kghub_downloader.download_utils import download_from_yaml

download_from_yaml(yaml_file="download.yaml", output_dir="data")
```

Command Line:
```
downloader --output_dir example_output --tags zfin_gene_to_phenotype example.yaml
```
Note: If your YAML file is named `download.yaml`, the argument can be omitted from the CLI call.  
For example, `downloader --output_dir example_output` is equivalent to `downloader --output_dir example_output download.yaml`

**Parameters:**  
- `yaml_file`: List of files to download in YAML format. Defaults to "download.yaml"  
- `output_dir`: Path to output directory. Defaults to current directory  
- `ignore_cache`: Optional boolean; if True ignores already downloaded files and download again. Defaults to False  
- `tags`: Optional list of tags, limits downloads to those with matching tags

