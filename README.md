# KG-Hub Downloader

This is a configuration based file caching downloader with initial support for http requests & queries against elasticsearch.

The YAML format for the download file is:

```
---
- 
  url: "http://example.com/myawesomefile.tsv"
  local_name: myawesomefile.tsv
-
  url: "http://example.com/myokfile.json"
  local_name: myokfile.json

```

Usage:

```
from kghub_downloader.download_utils import download_from_yaml

download_from_yaml(yaml_file="download.yaml", output_dir="data")
```
