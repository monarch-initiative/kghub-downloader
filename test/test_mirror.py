from sys import path as syspath
from os import path as ospath

#syspath.append("/home/glass/dev/tislab/kghub-downloader")
from kghub_downloader.download_utils import download_from_yaml

def test_mirror():
    if download_from_yaml(yaml_file="example/download.yaml", 
                    output_dir='.', 
                    mirror="gs://test-monarch-output/data", 
                    ignore_cache=True
                ):
        test = True
    assert test
      