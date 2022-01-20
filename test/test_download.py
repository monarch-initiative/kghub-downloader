from kghub_downloader.download_utils import download_from_yaml
from os.path import exists
import os

# Integration test using example configuration
def test_download():
    files = ["output/fish_phenotype.txt", "output/molecule.json", "output/merged_graph_stats.yaml"]

    for file in files:
        if exists(file):
            os.remove(file)

    download_from_yaml(yaml_file="example/download.yaml", output_dir="output")

    for file in files:
        assert exists(file)
        assert os.stat(file).st_size > 0

