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

The downloader requires a YAML file which contains a list of target URLs to download, and local names to save those downloads.  
For an example, see [example/download.yaml](example/download.yaml)

Available options are:
- \***url**: The URL to download from. Currently supported:  
  - `http(s)`
  - `ftp`
    - with `glob:` option to download files with specific extensions (only with ftp as of now and looks recursively).
  - Google Cloud Storage (`gs://`)
  - Google Drive (`gdrive://` or https://drive.google.com/...). The file must be publicly accessible.
  - Amazon AWS S3 bucket (`s3://`)
- **local_name**: The name to save the file as locally
- **tag**: A tag to use to filter downloads
- **api**: The API to use to download the file. Currently supported: `elasticsearch`
- elastic search options  
  - **query_file**: The file containing the query to run against the index
  - **index**: The elastic search index for query

> \* Note:  
>  Google Cloud Storage URLs require that you have set up your credentials as described [here](https://cloud.google.com/artifact-registry/docs/python/authentication#keyring-user). You must:  
> - [create a service account](https://cloud.google.com/iam/docs/service-accounts-create)  
> - [add the service account to the relevant bucket](https://cloud.google.com/storage/docs/access-control/using-iam-permissions#bucket-iam) and  
> - [download a JSON key](https://cloud.google.com/iam/docs/keys-create-delete) for that service account.  
>  Then, set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to that file.
>
> Mirorring local files to Amazon AWS S3 bucket requires the following:
>  - [Create an AWS account](https://portal.aws.amazon.com/)
>  - [Create an IAM user in AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started.html): This enables getting the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` needed for authentication. These two should be stored as environment variables in the user's system.
>  - [Create an S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html): This will be the destination for pushing local files.

You can also include any secrets like API keys you have set as environment variables using `{VARIABLE_NAME}`, for example:  
```yaml
---
- url: "https://example.com/myfancyfile.json?key={YOUR_SECRET}"
  localname: myfancyfile.json
```
Note: `YOUR_SECRET` *MUST* as an environment variable, and be sure to include the {curly braces} in the url string.

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

### Development

#### Install

```bash
git clone https://github.com/monarch-initiative/kghub-downloader.git
cd kghub-downloader
poetry install
```

#### Run tests

```bash
poetry run pytest
```

NOTE: The tests require gcloud credentials to be set up as described above, using the monarch github actions service account.