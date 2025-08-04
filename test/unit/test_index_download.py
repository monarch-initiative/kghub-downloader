import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from kghub_downloader.download import extract_ids_from_json, index_based_download
from kghub_downloader.model import DownloadableResource, DownloadOptions


class TestExtractIdsFromJson(unittest.TestCase):
    
    def test_extract_from_list(self):
        data = ["id1", "id2", "id3"]
        ids = extract_ids_from_json(data, "")
        self.assertEqual(ids, ["id1", "id2", "id3"])
    
    def test_extract_from_dict_with_lists(self):
        data = {
            "source1": ["id1", "id2"],
            "source2": ["id3", "id4"]
        }
        ids = extract_ids_from_json(data, "")
        self.assertEqual(set(ids), {"id1", "id2", "id3", "id4"})
    
    def test_extract_from_nested_structure_like_gocam(self):
        data = {
            "http://informatics.jax.org": ["27114 items"],
            "http://www.yeastgenome.org": ["8031 items"],
            "http://www.xenbase.org": [
                "5fb9cc0600000450",
                "5a7e68a100000569",
                "5a7e68a100001201"
            ]
        }
        ids = extract_ids_from_json(data, "")
        self.assertIn("5fb9cc0600000450", ids)
        self.assertIn("5a7e68a100000569", ids)
        self.assertIn("5a7e68a100001201", ids)
    
    def test_extract_with_path(self):
        data = {
            "results": {
                "models": ["model1", "model2", "model3"]
            }
        }
        ids = extract_ids_from_json(data, "results.models")
        self.assertEqual(ids, ["model1", "model2", "model3"])
    
    def test_extract_empty_data(self):
        data = {}
        ids = extract_ids_from_json(data, "")
        self.assertEqual(ids, [])


class TestIndexBasedDownload(unittest.TestCase):
    
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.test_output_dir = Path(self._tempdir.name)
    
    def tearDown(self):
        self._tempdir.cleanup()
    
    @patch('requests.get')
    def test_index_based_download_success(self, mock_get):
        # Mock the index response
        index_response = Mock()
        index_response.json.return_value = {
            "source1": ["id1", "id2"],
            "source2": ["id3"]
        }
        index_response.raise_for_status.return_value = None
        
        # Mock individual file responses
        file_response = Mock()
        file_response.iter_content.return_value = [b"test content"]
        file_response.raise_for_status.return_value = None
        
        # Configure mock to return different responses
        mock_get.side_effect = [index_response, file_response, file_response, file_response]
        
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json",
            url_pattern="https://example.com/files/{ID}.yaml",
            local_name="test.yaml"
        )
        
        options = DownloadOptions(progress=False, verbose=False)
        
        index_based_download(resource, self.test_output_dir, options)
        
        # Verify calls
        self.assertEqual(mock_get.call_count, 4)  # 1 index + 3 files
        
        # Check that files were created
        expected_files = ["id1.yaml", "id2.yaml", "id3.yaml"]
        for filename in expected_files:
            file_path = self.test_output_dir / filename
            self.assertTrue(file_path.exists(), f"File {filename} should exist")
    
    @patch('requests.get')
    def test_index_based_download_with_id_path(self, mock_get):
        # Mock the index response with nested structure
        index_response = Mock()
        index_response.json.return_value = {
            "results": {
                "models": ["model1", "model2"]
            }
        }
        index_response.raise_for_status.return_value = None
        
        # Mock individual file responses
        file_response = Mock()
        file_response.iter_content.return_value = [b"test content"]
        file_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [index_response, file_response, file_response]
        
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json",
            url_pattern="https://example.com/files/{ID}.yaml",
            id_path="results.models",
            local_name="test.yaml"
        )
        
        options = DownloadOptions(progress=False, verbose=False)
        
        index_based_download(resource, self.test_output_dir, options)
        
        # Check that files were created
        expected_files = ["model1.yaml", "model2.yaml"]
        for filename in expected_files:
            file_path = self.test_output_dir / filename
            self.assertTrue(file_path.exists(), f"File {filename} should exist")
    
    def test_missing_index_url(self):
        resource = DownloadableResource(
            url="index://test",
            url_pattern="https://example.com/files/{ID}.yaml"
        )
        
        options = DownloadOptions()
        
        with self.assertRaises(ValueError) as context:
            index_based_download(resource, self.test_output_dir, options)
        
        self.assertIn("index_url is required", str(context.exception))
    
    def test_missing_url_pattern(self):
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json"
        )
        
        options = DownloadOptions()
        
        with self.assertRaises(ValueError) as context:
            index_based_download(resource, self.test_output_dir, options)
        
        self.assertIn("url_pattern is required", str(context.exception))
    
    @patch('requests.get')
    def test_invalid_json_response(self, mock_get):
        # Mock the index response with invalid JSON
        index_response = Mock()
        index_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        index_response.raise_for_status.return_value = None
        
        mock_get.return_value = index_response
        
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json",
            url_pattern="https://example.com/files/{ID}.yaml"
        )
        
        options = DownloadOptions()
        
        with self.assertRaises(ValueError) as context:
            index_based_download(resource, self.test_output_dir, options)
        
        self.assertIn("Failed to parse index JSON", str(context.exception))
    
    @patch('requests.get')
    def test_no_ids_found(self, mock_get):
        # Mock the index response with no extractable IDs
        index_response = Mock()
        index_response.json.return_value = {"empty": "data"}
        index_response.raise_for_status.return_value = None
        
        mock_get.return_value = index_response
        
        resource = DownloadableResource(
            url="index://test",
            index_url="https://example.com/index.json",
            url_pattern="https://example.com/files/{ID}.yaml",
            id_path="nonexistent.path"
        )
        
        options = DownloadOptions()
        
        with self.assertRaises(ValueError) as context:
            index_based_download(resource, self.test_output_dir, options)
        
        self.assertIn("No IDs found in index data", str(context.exception))