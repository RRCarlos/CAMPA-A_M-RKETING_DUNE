"""
Generador de QRs con tokens reales del sistema HMAC-SHA256
"""

import qrcode
from PIL import Image, ImageDraw, ImageFont
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent
TOKENS_FILE = OUTPUT_DIR / "tokens_batch.json"

CITY_COLORS = {
    "Madrid": (0, 153, 204),
    "Barcelona": (204, 51, 0),
    "Valencia": (255, 102, 0)
}

def create_qr(data: str, size: int, color: tuple) -> Image.Image:
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=color, back_color="white")
    return img.resize((size, size), Image.Resampling.LANCZOS)

def add_label(img: Image.Image, city: str, num: int, font_size: int = 40) -> Image.Image:
    labeled = Image.new('RGB', (img.width, img.height + 80), 'white')
    labeled.paste(img, (0, 0))
    draw = ImageDraw.Draw(labeled)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
        font_bold = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()
        font_bold = font
    
    text = f"#{city.upper()} {num:02d}"
    bbox = draw.textbbox((0, 0), text, font=font_bold)
    text_width = bbox[2] - bbox[0]
    draw.text(((labeled.width - text_width) // 2, img.height + 15), text, fill="black", font=font_bold)
    return labeled

def main():
    # Cargar tokens
    with open(TOKENS_FILE, "r") as f:
        tokens = json.load(f)
    
    print(f"Cargados {len(tokens)} tokens")
    
    # Generar QRs estándar
    print("\n>> Generando QRs estandar...")
    for t in tokens:
        city = t["city"]
        num = t["num"]
        url = t["url"]
        color = CITY_COLORS[city]
        
        qr_img = create_qr(url, 800, color)
        labeled = add_label(qr_img, city, num)
        
        filename = f"QR_{city.upper()}_{num:02d}.png"
        labeled.save(OUTPUT_DIR / filename, "PNG", quality=95)
    
    print(f"[OK] {len(tokens)} QRs estandar generados")
    
    # Generar QRs gigantes
    print("\n>> Generando QRs gigantes...")
    for city_code, city_name in [("MAD", "Madrid"), ("BCN", "Barcelona"), ("VLC", "Valencia")]:
        # Usar el primer token de cada ciudad
        token_data = next(t for t in tokens if t["city_code"] == city_code)
        url = token_data["url"]
        color = CITY_COLORS[city_name]
        
        qr_img = create_qr(url, 4000, color)
        filename = f"QR_GIGANTE_{city_name.upper()}.png"
        qr_img.save(OUTPUT_DIR / filename, "PNG", quality=100)
        print(f"  [OK] {filename} (2m x 2m)")
    
    print("\n>> QRs regenerados con tokens HMAC-SHA256!")

if __name__ == "__main__":
    main()
