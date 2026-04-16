import qrcode
import qrcode.image.pure
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

# Configuración
OUTPUT_DIR = Path(r"C:\Users\PC\OneDrive\Desktop\CAMPAÑA_MÁRKETING\QR_CODES")
QR_COUNT_PER_CITY = 10

# Ciudades y prefijos
CITIES = {
    "Madrid": "cs.mad",
    "Barcelona": "cs.bcn",
    "Valencia": "cs.vlc"
}

# Colores por ciudad (estilo gamificado)
CITY_COLORS = {
    "Madrid": (0, 153, 204),    # Azul Madrid
    "Barcelona": (204, 51, 0),   # Azulgrana
    "Valencia": (255, 102, 0)    # Naranja Valencia
}

def generate_qr_token(city: str, index: int) -> str:
    """Genera un token único para el QR (placeholder hasta implementación real)."""
    city_code = CITIES[city].split('.')[1].upper()
    return f"{city_code}-{index:03d}"

def create_qr_with_border(data: str, size: int, color: tuple, border_size: int = 4) -> Image.Image:
    """Crea un QR con borde y fondo."""
    # Crear QR
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=border_size,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Crear imagen del QR
    qr_img = qr.make_image(fill_color=color, back_color="white")
    qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)
    
    return qr_img

def add_label(img: Image.Image, city: str, index: int, font_size: int = 40) -> Image.Image:
    """Añade etiqueta con ciudad y número al QR."""
    labeled_img = Image.new('RGB', (img.width, img.height + 80), 'white')
    labeled_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(labeled_img)
    
    # Usar fuente del sistema
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
        font_bold = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()
        font_bold = font
    
    # Texto centrado
    text = f"#{city.upper()} {index:02d}"
    bbox = draw.textbbox((0, 0), text, font=font_bold)
    text_width = bbox[2] - bbox[0]
    text_x = (labeled_img.width - text_width) // 2
    text_y = img.height + 15
    
    draw.text((text_x, text_y), text, fill="black", font=font_bold)
    
    return labeled_img

def generate_standard_qr(city: str, index: int, output_dir: Path, size: int = 800):
    """Genera un QR estándar (800x800px = ~10cm a 200dpi)."""
    token = generate_qr_token(city, index)
    url = f"https://{CITIES[city]}/{token}"
    
    color = CITY_COLORS[city]
    qr_img = create_qr_with_border(url, size, color)
    labeled_img = add_label(qr_img, city, index)
    
    filename = f"QR_{city.upper()}_{index:02d}.png"
    labeled_img.save(output_dir / filename, "PNG", quality=95)
    print(f"  [OK] Generado: {filename}")

def generate_giant_qr(city: str, output_dir: Path, size: int = 4000):
    """Genera QR gigante 2x2 metros (4000x4000px a 200dpi)."""
    token = generate_qr_token(city, 0)
    url = f"https://{CITIES[city]}/{token}"
    
    color = CITY_COLORS[city]
    qr_img = create_qr_with_border(url, size, color, border_size=8)
    
    filename = f"QR_GIGANTE_{city.upper()}.png"
    qr_img.save(output_dir / filename, "PNG", quality=100)
    print(f"  [OK] Generado: {filename} (2m x 2m @ 200dpi)")

def main():
    # Crear directorio de salida
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("GENERADOR DE CODIGOS QR - CIUDAD SECRETA")
    print("=" * 60)
    
    # Generar QRs estándar por ciudad
    for city in CITIES.keys():
        print(f"\n>> {city}:")
        for i in range(1, QR_COUNT_PER_CITY + 1):
            generate_standard_qr(city, i, OUTPUT_DIR)
    
    # Generar QRs gigantes
    print(f"\n" + "=" * 60)
    print(">> QRs GIGANTES (2m x 2m):")
    print("=" * 60)
    for city in CITIES.keys():
        generate_giant_qr(city, OUTPUT_DIR)
    
    # Resumen
    total = len(CITIES) * QR_COUNT_PER_CITY + len(CITIES)
    print(f"\n{'=' * 60}")
    print(f"> TOTAL GENERADOS: {total} codigos QR")
    print(f"   - {len(CITIES) * QR_COUNT_PER_CITY} QRs estandar")
    print(f"   - {len(CITIES)} QRs gigantes (2x2m)")
    print(f"\n> Carpeta: {OUTPUT_DIR}")
    print("=" * 60)
    
    # Lista de archivos
    print("\n> CONTENIDO:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        size_kb = f.stat().st_size // 1024
        print(f"   {f.name} ({size_kb} KB)")

if __name__ == "__main__":
    main()
