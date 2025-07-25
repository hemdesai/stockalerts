"""OCR crypto images to find derivative exposures table."""
import os
import base64
import requests
from app.core.config import settings

crypto_images_dir = "crypto_images"
images = sorted([f for f in os.listdir(crypto_images_dir) if f.endswith('.png')])

print("Searching for DERIVATIVE EXPOSURES table with risk ranges...")
print("=" * 60)

for img_file in images[:5]:  # Check first 5 images
    img_path = os.path.join(crypto_images_dir, img_file)
    print(f"\nProcessing {img_file}...")
    
    try:
        # Read image
        with open(img_path, 'rb') as f:
            image_data = f.read()
        
        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        data_url = f"data:image/png;base64,{image_base64}"
        
        # Call Mistral OCR API
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "document": {"image_url": data_url},
            "model": "mistral-ocr-latest"
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/ocr",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            ocr_data = response.json()
            ocr_text = ocr_data['pages'][0]['markdown']
            
            # Check if it contains derivative exposures
            if "DERIVATIVE" in ocr_text.upper() and "EXPOSURE" in ocr_text.upper():
                print(f"✓ Found DERIVATIVE EXPOSURES in {img_file}!")
                print("-" * 60)
                
                # Look for the table with tickers
                lines = ocr_text.split('\n')
                in_table = False
                for line in lines:
                    line_upper = line.upper()
                    
                    # Start of table
                    if "DERIVATIVE" in line_upper and "EXPOSURE" in line_upper:
                        in_table = True
                        print(line)
                    elif "RISK RANGE" in line_upper:
                        print(line)
                    elif in_table and "|" in line:
                        # Table row
                        print(line)
                    elif in_table and any(ticker in line_upper for ticker in ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN']):
                        print(line)
                
                # Save full OCR
                with open(f'ocr_{img_file}.txt', 'w', encoding='utf-8') as f:
                    f.write(ocr_text)
                print(f"\nSaved full OCR to: ocr_{img_file}.txt")
                print("-" * 60)
            else:
                print(f"No derivative exposures table found in {img_file}")
        else:
            print(f"OCR failed: {response.status_code}")
            
    except Exception as e:
        print(f"Error processing {img_file}: {e}")

print("\nDone.")