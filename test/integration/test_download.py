import os
from os.path import exists

from kghub_downloader.download_utils import download_from_yaml


# Integration test using example configuration
def test_download():
    files = files = [
        "test/output/zfin/fish_phenotype.txt",
        "test/output/test_file.yaml",
        "test/output/gdrive_test_1.txt",
        "test/output/gdrive_test_2.txt",
        "test/output/testfile.zip",
    ]

    for file in files:
        if exists(file):
            os.remove(file)

    download_from_yaml(yaml_file="example/download.yaml", output_dir="test/output")

    for file in files:
        assert exists(file)
        assert os.stat(file).st_size > 0


def test_tag():
    files = ["test/output/zfin/fish_phenotype.txt", "test/output/test_file.yaml"]
    tagged_files = ["test/output/gdrive_test_1.txt"]

    for file in files:
        if exists(file):
            os.remove(file)

    download_from_yaml(
        yaml_file="example/download.yaml", output_dir="test/output", tags=["testing"]
    )

    for file in tagged_files:
        assert exists(file)
        assert os.stat(file).st_size > 0

    for file in files:
        if file not in tagged_files:
            assert not exists(file)
