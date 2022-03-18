"""
TODO 
- mock GCS calls, maybe fake datafile too? 
"""
from sys import path as syspath
from os import path as ospath

syspath.append("/home/glass/dev/tislab/kghub-downloader")
from kghub_downloader.download_utils import *

# proper test
def test_mirror():
    mirror_to_bucket(
               local_file='resources/testfile.txt',
               bucket_url='gs://test-monarch-output',
               remote_file='test/test.txt'
          )
