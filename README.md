# CIUDAD SECRETA - Sistema de Códigos QR

## ¿Qué es este proyecto?

**Ciudad Secreta** es una campaña de marketing gamificada para tres ciudades españolas: Madrid, Barcelona y Valencia. Los usuarios ("Desveladores") exploran la ciudad escaneando códigos QR físicos, completando misiones y subiendo de nivel tipo RPG.

Este repositorio contiene el **sistema técnico** para generar y validar los códigos QR de la campaña.

---

## ⚠️ SEGURIDAD - Archivos que NO se suben al repo

**NUNCA subir estas carpetas a GitHub:**

| Carpeta | Contenido |
|---------|-----------|
| `data/` | tokens.db, tokens_batch.json |
| `config/` | .env, _CLAVES_CONFIDENCIAL.txt |

---

## Estructura del proyecto

```
CAMPA-A_M-RKETING_DUNE/
│
├── 📄 README.md                          ← Este archivo
├── 📄 .gitignore                        ← Archivos excluidos
│
├── 📁 docs/                             ← Documentación de campaña
│   ├── CIUDAD_SECRETA_v2.txt
│   ├── CIUDAD_SECRETA_v2.pdf
│   ├── CAMPAÑA_MARKETING.txt
│   └── campaña_marketing_optimizada.docx
│
├── 📁 src/                              ← Código fuente
│   ├── server.py                        ← Servidor FastAPI
│   ├── token_system.py                  ← CLI para tokens
│   ├── generate_qr.py                   ← Generador de QRs
│   └── regenerate_with_real_tokens.py   ← Regenerador con claves reales
│
├── 📁 assets/qr/                       ← Códigos QR generados
│   ├── barcelona/
│   │   ├── QR_BARCELONA_01.png ... 10
│   ├── madrid/
│   │   ├── QR_MADRID_01.png ... 10
│   ├── valencia/
│   │   ├── QR_VALENCIA_01.png ... 10
│   └── gigante/
│       ├── QR_GIGANTE_MADRID.png
│       ├── QR_GIGANTE_BARCELONA.png
│       └── QR_GIGANTE_VALENCIA.png
│
├── 📁 data/                             ← DATOS SENSIBLES (NO SUBIR)
│   ├── .gitkeep
│   ├── tokens.db                        ← Base de datos SQLite
│   └── tokens_batch.json                ← Tokens exportados
│
└── 📁 config/                           ← CONFIGURACIÓN (NO SUBIR)
    ├── .gitkeep
    ├── .env.example                     ← Plantilla
    ├── .env                             ← Variables de entorno
    └── _CLAVES_CONFIDENCIAL.txt         ← Claves secretas
```

---

## 🔐 Configuración de seguridad

### 1. Archivos de configuración

Copiar `.env.example` a `.env`:

```bash
cd config
cp .env.example .env
# Editar .env y añadir SECRET_KEY
```

### 2. Generar SECRET_KEY

**Opción A: Generar automáticamente**
```bash
openssl rand -hex 32
```

**Opción B: Python**
```python
import secrets
print(secrets.token_hex(32))
```

### 3. IMPORTANTE

La `SECRET_KEY` debe ser **la misma** en:
- `src/server.py` (servidor)
- `src/token_system.py` (CLI)
- `config/.env` (configuración)

Si cambias la clave, los tokens existentes dejarán de funcionar.

---

## Instalación

```bash
# Clonar repositorio
git clone https://github.com/RRCarlos/CAMPA-A_M-RKETING_DUNE.git
cd CAMPA-A_M-RKETING_DUNE

# Crear carpeta data (para tokens.db y tokens_batch.json)
mkdir -p data

# Crear carpeta config (para .env)
mkdir -p config
cp config/.env.example config/.env

# Instalar dependencias
pip install fastapi uvicorn[standard] qrcode pillow python-dotenv

# Editar config/.env y añadir SECRET_KEY

# Iniciar servidor
python src/server.py
```

---

## Uso rápido

### Servidor API

```bash
python src/server.py
# Disponible en: http://localhost:8000
# Documentación: http://localhost:8000/docs
```

### CLI de tokens

```bash
# Ver ayuda
python src/token_system.py --help

# Ver estadísticas
python src/token_system.py stats

# Generar nuevos tokens
python src/token_system.py generate -c MAD -n 10

# Validar token
python src/token_system.py validate <token>

# Marcar token como usado
python src/token_system.py validate <token> --use --user usuario_123
```

---

## Endpoints del servidor

| Método | URL | Descripción |
|--------|-----|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Estado del servicio |
| `GET` | `/api/v1/validate/{token}` | Verificar token |
| `POST` | `/api/v1/scan` | Escanear (marca usado) |
| `POST` | `/api/v1/generate` | Crear token |
| `GET` | `/api/v1/stats` | Estadísticas |
| `GET` | `/go/{token}` | Redirección QR |

---

## Tokens existentes

Se han generado **30 tokens** (10 por ciudad) que están en `data/tokens_batch.json`.

Los tokens actuales usan una SECRET_KEY temporal. Para regenerarlos con la clave definitiva:

```bash
# 1. Configurar SECRET_KEY en config/.env
# 2. Regenerar tokens
python src/token_system.py batch --per-city 10

# 3. Regenerar QRs
python src/regenerate_with_real_tokens.py
```

---

## Códigos QR

### Estándar (10 por ciudad)
- `assets/qr/madrid/QR_MADRID_01.png` ... `QR_MADRID_10.png`
- `assets/qr/barcelona/QR_BARCELONA_01.png` ... `QR_BARCELONA_10.png`
- `assets/qr/valencia/QR_VALENCIA_01.png` ... `QR_VALENCIA_10.png`

**Tamaño:** 800x800 px (~10cm a 200dpi)

### Gigantes (Launch Day)
- `assets/qr/gigante/QR_GIGANTE_MADRID.png`
- `assets/qr/gigante/QR_GIGANTE_BARCELONA.png`
- `assets/qr/gigante/QR_GIGANTE_VALENCIA.png`

**Tamaño:** 4000x4000 px (2m x 2m a 200dpi)

---

## Dependencias

```
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
pydantic>=2.0.0
qrcode>=7.4.0
Pillow>=10.0.0
python-dotenv>=1.0.0
```

---

## Producción

### Servidor

```bash
# VPS mínimo recomendado
# - 1 vCPU, 1GB RAM, 10GB SSD
# - Ubuntu 22.04

# Instalar
apt update && apt install python3 python3-pip nginx
pip install fastapi uvicorn[standard] qrcode pillow python-dotenv gunicorn

# Configurar nginx como reverse proxy
# Configurar DNS: cs.mad, cs.bcn, cs.vlc -> IP del servidor

# Iniciar con gunicorn
cd src
gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:8000
```

### IMPORTANTE: SECRET_KEY en producción

```bash
# Definir variable de entorno ANTES de iniciar
export SECRET_KEY="TU_CLAVE_SEGURA_DE_64_CARACTERES"
python src/server.py
```

---

## Licencia

Copyright © 2024 Ciudad Secreta. Todos los derechos reservados.
