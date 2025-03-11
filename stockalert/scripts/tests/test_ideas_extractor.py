import pytest
import os
import json
from pathlib import Path
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock

# Now import the IdeasEmailExtractor with mocked BaseEmailExtractor
with patch.dict('sys.modules', {'stockalert.scripts.email_extractors.BaseEmailExtractor': MagicMock()}):
    from ..email_extractors.ideas_extractor import IdeasEmailExtractor, IdeasData, IdeasAsset


@pytest.fixture
def ideas_extractor():
    return IdeasEmailExtractor()


@pytest.fixture
def sample_ideas_data():
    return {
        "assets": [
            {
                "ticker": "TKO",
                "sentiment": "BULLISH",
                "buy_trade": 144.00,
                "sell_trade": 175.00,
                "category": "ideas"
            },
            {
                "ticker": "HUBS",
                "sentiment": "BULLISH",
                "buy_trade": 705.00,
                "sell_trade": 799.00,
                "category": "ideas"
            },
            {
                "ticker": "BYD",
                "sentiment": "BULLISH",
                "buy_trade": 73.54,
                "sell_trade": 79.92,
                "category": "ideas"
            },
            {
                "ticker": "MPW",
                "sentiment": "BEARISH",
                "buy_trade": 4.35,
                "sell_trade": 6.25,
                "category": "ideas"
            },
            {
                "ticker": "AMAT",
                "sentiment": "BEARISH",
                "buy_trade": 153.00,
                "sell_trade": 177.00,
                "category": "ideas"
            }
        ]
    }


def test_ideas_asset_model():
    """Test the IdeasAsset Pydantic model"""
    asset = IdeasAsset(
        ticker="TKO",
        sentiment="BULLISH",
        buy_trade=144.00,
        sell_trade=175.00
    )
    
    assert asset.ticker == "TKO"
    assert asset.sentiment == "BULLISH"
    assert asset.buy_trade == 144.00
    assert asset.sell_trade == 175.00
    assert asset.category == "ideas"  # Default value


def test_ideas_data_model(sample_ideas_data):
    """Test the IdeasData Pydantic model"""
    assets = [
        IdeasAsset(**asset_data)
        for asset_data in sample_ideas_data["assets"]
    ]
    
    data = IdeasData(assets=assets)
    
    assert len(data.assets) == 5
    assert data.assets[0].ticker == "TKO"
    assert data.assets[1].ticker == "HUBS"
    assert data.assets[2].ticker == "BYD"
    assert data.assets[3].ticker == "MPW"
    assert data.assets[4].ticker == "AMAT"


@patch('..email_extractors.ideas_extractor.Mistral')
def test_process_image(mock_mistral, ideas_extractor, sample_ideas_data):
    """Test the process_image method with mocked Mistral client"""
    # Mock the Mistral OCR response
    mock_ocr_response = MagicMock()
    mock_ocr_response.pages = [MagicMock()]
    mock_ocr_response.pages[0].markdown = """
    # Longs
    | STOCK | CLOSING PRICE 2/28 | TREND RANGES |
    | ----- | ------------------ | ------------ |
    | TKO   | $150.67            | $144.00      | $175.00 |
    | HUBS  | $724.42            | $705.00      | $799.00 |
    | BYD   | $76.27             | $73.54       | $79.92  |
    
    # Shorts
    | STOCK | CLOSING PRICE 2/28 | TREND RANGES |
    | ----- | ------------------ | ------------ |
    | MPW   | $5.90              | $4.35        | $6.25   |
    | AMAT  | $158.07            | $153.00      | $177.00 |
    """
    
    # Mock the Mistral chat response
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [MagicMock()]
    mock_chat_response.choices[0].message = MagicMock()
    
    # Create a real IdeasData object for the parsed response
    assets = [IdeasAsset(**asset_data) for asset_data in sample_ideas_data["assets"]]
    ideas_data = IdeasData(assets=assets)
    mock_chat_response.choices[0].message.parsed = ideas_data
    
    # Set up the mock Mistral client
    mock_mistral_instance = mock_mistral.return_value
    mock_mistral_instance.ocr.process.return_value = mock_ocr_response
    mock_mistral_instance.chat.parse.return_value = mock_chat_response
    
    # Create a mock image
    image_data = b"mock_image_data"
    
    # Call the method
    result = ideas_extractor.process_image(image_data)
    
    # Verify the result
    assert len(result) == 5
    assert result[0]["ticker"] == "TKO"
    assert result[0]["sentiment"] == "BULLISH"
    assert result[0]["buy_trade"] == 144.00
    assert result[0]["sell_trade"] == 175.00
    assert result[0]["category"] == "ideas"


@patch.object(IdeasEmailExtractor, 'extract_image_from_email')
@patch.object(IdeasEmailExtractor, 'process_image')
@patch.object(IdeasEmailExtractor, 'cleanup_temp_files')
def test_extract_ideas_data(mock_cleanup, mock_process, mock_extract, ideas_extractor, sample_ideas_data):
    """Test the extract_ideas_data method with mocked dependencies"""
    # Mock the extract_image_from_email method
    mock_extract.return_value = b"mock_image_data"
    
    # Mock the process_image method
    mock_process.return_value = sample_ideas_data["assets"]
    
    # Call the method
    result = ideas_extractor.extract_ideas_data()
    
    # Verify the result
    assert result is True
    mock_extract.assert_called_once()
    mock_process.assert_called_once_with(b"mock_image_data")
    mock_cleanup.assert_called_once()


def test_cleanup_temp_files(ideas_extractor):
    """Test the cleanup_temp_files method"""
    # Create temporary files for testing
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / 'data'
    data_dir.mkdir(exist_ok=True)
    
    # Create test files
    test_files = [
        data_dir / 'ideas_email_raw.html',
        data_dir / 'ideas_table.png',
        data_dir / 'ideas_test.png'
    ]
    
    for file_path in test_files:
        with open(file_path, 'w') as f:
            f.write('test content')
    
    # Call the cleanup method
    ideas_extractor.cleanup_temp_files()
    
    # Verify files were deleted
    for file_path in test_files:
        assert not file_path.exists()


if __name__ == '__main__':
    # Create an instance of the extractor
    extractor = IdeasEmailExtractor()
    
    # Run the extraction
    extractor.extract_ideas_data()
    
    # Print CSV location
    project_root = Path(__file__).parent.parent.parent
    print(f"CSV saved to: {project_root / 'data' / 'ideas.csv'}")