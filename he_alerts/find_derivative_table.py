"""Find the derivative exposures table with risk ranges."""
import os
from PIL import Image
import pytesseract
import re

# Configure tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

crypto_images_dir = "crypto_images"
images = sorted([f for f in os.listdir(crypto_images_dir) if f.endswith('.png')])

print("Searching for DERIVATIVE EXPOSURES table with risk ranges...")
print("=" * 60)

for img_file in images:
    img_path = os.path.join(crypto_images_dir, img_file)
    print(f"\nChecking {img_file}...")
    
    try:
        # Open and OCR the image
        image = Image.open(img_path)
        text = pytesseract.image_to_string(image)
        
        # Check if it contains derivative exposures with risk ranges
        if "DERIVATIVE" in text.upper() and ("RISK RANGE" in text.upper() or "BUY TRADE" in text.upper()):
            print(f"✓ Found DERIVATIVE EXPOSURES table in {img_file}!")
            print("-" * 60)
            
            # Extract lines that might contain ticker data
            lines = text.split('\n')
            for line in lines:
                # Look for lines with tickers and numbers
                if any(ticker in line.upper() for ticker in ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN', 'BITO', 'ARKB']):
                    print(line)
                elif "DERIVATIVE" in line.upper() or "RISK RANGE" in line.upper():
                    print(line)
                elif "|" in line and any(char.isdigit() for char in line):
                    print(line)
            
            print("-" * 60)
            
            # Save the full text
            with open(f'derivative_table_{img_file}.txt', 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Saved full OCR to: derivative_table_{img_file}.txt")
            
    except Exception as e:
        print(f"Error processing {img_file}: {e}")

print("\nDone searching.")