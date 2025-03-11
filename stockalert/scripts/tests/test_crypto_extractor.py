import unittest
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from scripts.email_extractors.crypto_extractor import CryptoEmailExtractor, CryptoData


class TestCryptoExtractor(unittest.TestCase):
    def setUp(self):
        # Create a mock for the Mistral client
        self.mistral_patcher = patch('scripts.email_extractors.crypto_extractor.Mistral')
        self.mock_mistral = self.mistral_patcher.start()
        
        # Create a mock instance of the Mistral client
        self.mock_mistral_instance = MagicMock()
        self.mock_mistral.return_value = self.mock_mistral_instance
        
        # Setup mock response for chat method
        self.mock_chat_response = MagicMock()
        self.mock_choice = MagicMock()
        self.mock_message = MagicMock()
        
        # Sample JSON response that Mistral would return
        self.sample_json = {
            "assets": [
                {
                    "ticker": "BTC",
                    "sentiment": "BEARISH",
                    "buy_trade": 80012.0,
                    "sell_trade": 93968.0,
                    "category": "digitalassets"
                },
                {
                    "ticker": "ETH",
                    "sentiment": "BEARISH",
                    "buy_trade": 2015.0,
                    "sell_trade": 2498.0,
                    "category": "digitalassets"
                },
                {
                    "ticker": "SOL",
                    "sentiment": "BEARISH",
                    "buy_trade": 121.0,
                    "sell_trade": 167.0,
                    "category": "digitalassets"
                },
                {
                    "ticker": "AVAX",
                    "sentiment": "BEARISH",
                    "buy_trade": 19.16,
                    "sell_trade": 24.22,
                    "category": "digitalassets"
                },
                {
                    "ticker": "XRP",
                    "sentiment": "BEARISH",
                    "buy_trade": 1.88,
                    "sell_trade": 2.81,
                    "category": "digitalassets"
                }
            ]
        }
        
        # Set up the mock response
        self.mock_message.content = f"```json\n{json.dumps(self.sample_json)}\n```"
        self.mock_choice.message = self.mock_message
        self.mock_chat_response.choices = [self.mock_choice]
        
        # Make the chat method return our mock response
        self.mock_mistral_instance.chat.return_value = self.mock_chat_response
        
        # Create a mock for the BaseEmailExtractor.get_email_content method
        self.get_email_content_patcher = patch('scripts.email_extractors.BaseEmailExtractor.get_email_content')
        self.mock_get_email_content = self.get_email_content_patcher.start()
        
        # Sample HTML content with an image
        self.sample_html = """
        <html>
        <body>
            <h1>CRYPTO QUANT</h1>
            <img src="https://d1abcdefghijk.cloudfront.net/crypto_image.png" />
        </body>
        </html>
        """
        self.mock_get_email_content.return_value = self.sample_html
        
        # Create a mock for requests.get
        self.requests_patcher = patch('requests.get')
        self.mock_requests_get = self.requests_patcher.start()
        
        # Setup mock response for requests.get
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.content = b'fake_image_data'
        self.mock_requests_get.return_value = self.mock_response
        
        # Create the extractor instance
        self.extractor = CryptoEmailExtractor()
        
        # Create data directory if it doesn't exist
        self.data_dir = project_root / 'data'
        self.data_dir.mkdir(exist_ok=True)

    def tearDown(self):
        # Stop all patches
        self.mistral_patcher.stop()
        self.get_email_content_patcher.stop()
        self.requests_patcher.stop()
        
        # Clean up any test files
        test_files = [
            'crypto_email_raw.html',
            'crypto_table.png',
            'crypto_cloudfront_image_14.png',
            'digitalassets.csv'
        ]
        
        for file in test_files:
            file_path = self.data_dir / file
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

    def test_extract_image_from_email(self):
        """Test extracting image from email"""
        image_data = self.extractor.extract_image_from_email()
        
        # Verify that get_email_content was called with the correct query
        self.mock_get_email_content.assert_called_once()
        call_args = self.mock_get_email_content.call_args[0][0]
        self.assertIn('subject:"CRYPTO QUANT"', call_args)
        self.assertIn('after:', call_args)
        
        # Verify that requests.get was called to download the image
        self.mock_requests_get.assert_called()
        
        # Verify that image data was returned
        self.assertEqual(image_data, b'fake_image_data')

    def test_process_image(self):
        """Test processing image with Mistral OCR"""
        # Call the process_image method with fake image data
        result = self.extractor.process_image(b'fake_image_data')
        
        # Verify that Mistral chat was called
        self.mock_mistral_instance.chat.assert_called_once()
        
        # Verify that the result matches our sample data
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['ticker'], 'BTC')
        self.assertEqual(result[0]['sentiment'], 'BEARISH')
        self.assertEqual(result[0]['buy_trade'], 80012.0)
        self.assertEqual(result[0]['sell_trade'], 93968.0)
        
        # Verify that CSV file was created
        csv_path = self.data_dir / 'digitalassets.csv'
        self.assertTrue(csv_path.exists())

    def test_extract(self):
        """Test the full extraction process"""
        # Call the extract method
        result = self.extractor.extract()
        
        # Verify that extract_image_from_email and process_image were both called
        # (implicitly verified by checking the result)
        
        # Verify that the result matches our sample data
        self.assertEqual(len(result), 5)
        
        # Check that all assets have the correct category
        for asset in result:
            self.assertEqual(asset['category'], 'digitalassets')
        
        # Verify that all expected cryptocurrencies are present
        tickers = [asset['ticker'] for asset in result]
        expected_tickers = ['BTC', 'ETH', 'SOL', 'AVAX', 'XRP']
        for ticker in expected_tickers:
            self.assertIn(ticker, tickers)


if __name__ == '__main__':
    unittest.main()