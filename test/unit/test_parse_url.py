from kghub_downloader.download_utils import *

import os, pytest

os.environ["TEST_URL"] = "https://testurl.com/fake/download/rootpath"
os.environ["TEST_KEY"] = "123456789987654321"


@pytest.mark.parametrize(
    "test_url",
    ["{TEST_URL}/fakefile.txt?key={TEST_KEY}"],
)
def test_parse_url(test_url):
    parsed = parse_url(test_url)
    assert (
        parsed
        == "https://testurl.com/fake/download/rootpath/fakefile.txt?key=123456789987654321"
    )
