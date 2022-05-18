from kghub_downloader.download_utils import download_from_yaml
from os.path import exists
import os


# Integration test using example configuration
def test_download():
    files = ["test/output/zfin/fish_phenotype.txt"]#, "test/output/merged_graph_stats.yaml"]

    for file in files:
        if exists(file):
            os.remove(file)

    download_from_yaml(yaml_file="test/resources/download.yaml", output_dir="test/output")

    for file in files:
        assert exists(file)
        assert os.stat(file).st_size > 0


# def test_tag():
#     files = ["test/output/fish_phenotype.txt", "test/output/merged_graph_stats.yaml"]
#     tagged_files = ["test/output/merged_graph_stats.yaml"]

#     for file in files:
#         if exists(file):
#             os.remove(file)

#     download_from_yaml(yaml_file="test/resources/download.yaml",
#                        output_dir="test/output",
#                        tags=['graph_stats'])

#     for file in tagged_files:
#         assert exists(file)
#         assert os.stat(file).st_size > 0

#     for file in files:
#         if file not in tagged_files:
#             assert not exists(file)
