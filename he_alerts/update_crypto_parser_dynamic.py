"""Update crypto parser to handle dynamic derivative exposures table."""

# Updated parse_derivative_exposures_table function
derivative_exposures_code = '''def parse_derivative_exposures_table(ocr_text: str) -> List[Dict[str, any]]:
    """
    Parse the Derivative Exposures table from OCR text.
    This table contains crypto-related stocks like IBIT, MSTR, MARA, RIOT, etc.
    
    Args:
        ocr_text: OCR output text
        
    Returns:
        List of extracted crypto-related stock data
    """
    stocks = []
    lines = ocr_text.split('\\n')
    
    try:
        # Find the table header
        header_found = False
        in_table = False
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            
            # Look for table header
            if "DIRECT & DERIVATIVE EXPOSURES" in line_upper or "RISK RANGE & TREND SIGNAL" in line_upper:
                header_found = True
                logger.info(f"Found derivative exposures header at line {i}: {line}")
                continue
            
            # Look for column headers
            if header_found and ("TICKER" in line_upper or ("BUY TRADE" in line_upper and "SELL TRADE" in line_upper)):
                in_table = True
                logger.info(f"Found table columns at line {i}")
                continue
            
            if not in_table:
                continue
            
            # Skip empty lines
            if not line.strip():
                continue
                
            # End of table detection
            if in_table and ("---" in line or "___" in line or len(line.strip()) < 3):
                # Might be end of table
                if len(stocks) > 0:  # If we already found some stocks, stop
                    break
            
            # Parse data rows - look for lines with multiple values separated by spaces or pipes
            parts = []
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
            else:
                # Split by multiple spaces
                parts = line.split()
            
            if len(parts) >= 4:  # Need at least ticker, price, buy, sell
                potential_ticker = parts[0].strip().upper()
                
                # Validate ticker - should be 3-5 uppercase letters
                if re.match(r'^[A-Z]{3,5}$', potential_ticker):
                    try:
                        # Extract numeric values from remaining parts
                        numbers = []
                        for part in parts[1:]:
                            # Remove dollar signs, commas, percentages
                            cleaned = re.sub(r'[$,%]', '', part)
                            try:
                                num = float(cleaned)
                                numbers.append(num)
                            except:
                                continue
                        
                        if len(numbers) >= 3:  # Need at least price, buy, sell
                            # Usually: current price, buy trade, sell trade
                            price = numbers[0]
                            buy_trade = numbers[1]
                            sell_trade = numbers[2]
                            
                            # Determine sentiment from the line or trend signal column
                            sentiment = "neutral"
                            if "BULLISH" in line_upper:
                                sentiment = "bullish"
                            elif "BEARISH" in line_upper:
                                sentiment = "bearish"
                            
                            stock = {
                                "ticker": potential_ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_trade,
                                "sell_trade": sell_trade,
                                "category": "digitalassets"
                            }
                            stocks.append(stock)
                            logger.info(f"Extracted {potential_ticker}: Price=${price}, Buy=${buy_trade}, Sell=${sell_trade}, Sentiment={sentiment}")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing line '{line}': {e}")
        
        # If no stocks found, try more flexible parsing
        if len(stocks) == 0:
            logger.info("No stocks found with strict parsing, trying flexible approach")
            # Look for any line with a valid ticker and numbers
            for line in lines:
                # Common crypto stock tickers
                crypto_stock_tickers = ['IBIT', 'MSTR', 'MARA', 'RIOT', 'ETHA', 'BLOK', 'COIN', 'BITO', 
                                       'ARKB', 'BTCO', 'FBTC', 'GBTC', 'BITF', 'HUT', 'CLSK']
                
                for ticker in crypto_stock_tickers:
                    if ticker in line.upper():
                        # Extract numbers from this line
                        numbers = re.findall(r'\\$?([\\d,]+\\.?\\d*)', line)
                        if len(numbers) >= 3:
                            try:
                                buy_trade = float(numbers[1].replace(',', ''))
                                sell_trade = float(numbers[2].replace(',', ''))
                                
                                sentiment = "bullish" if "BULLISH" in line.upper() else "bearish" if "BEARISH" in line.upper() else "neutral"
                                
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "digitalassets"
                                }
                                stocks.append(stock)
                                logger.info(f"Flexibly extracted {ticker}: Buy=${buy_trade}, Sell=${sell_trade}")
                                break
                            except:
                                continue
        
        logger.info(f"Total derivative exposures extracted: {len(stocks)}")
        
    except Exception as e:
        logger.error(f"Error parsing derivative exposures table: {e}")
    
    return stocks
'''

print("Updated parse_derivative_exposures_table function to dynamically extract crypto stocks")
print("=" * 80)
print(derivative_exposures_code)