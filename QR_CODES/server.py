"""
Ciudad Secreta - Servidor de Validación de Tokens QR
====================================================

FastAPI server que valida tokens y marca como usados.

Uso:
    uvicorn server:app --reload --port 8000
"""

import sys
import hmac
import hashlib
import time
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ============================================================
# CONFIGURACIÓN
# ============================================================

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Clave secreta para tokens HMAC-SHA256
# IMPORTANTE: Esta clave DEBE ser la misma para generar y validar tokens
# En producción: definir SECRET_KEY en variable de entorno
# En desarrollo: se genera automáticamente (tokens no serán compatibles entre ejecuciones)
SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    print("=" * 60)
    print("ATENCION: SECRET_KEY no encontrada en variables de entorno")
    print("Los tokens generados seran incompatibles con los existentes.")
    print("Para desarrollo, crear archivo .env con SECRET_KEY.")
    print("=" * 60)
    SECRET_KEY = secrets.token_hex(32)
else:
    print(f"[OK] SECRET_KEY cargada de variables de entorno")

DB_PATH = Path(__file__).parent / "tokens.db"
TOKEN_EXPIRY_HOURS = 24

CITIES = {
    "MAD": "Madrid",
    "BCN": "Barcelona",
    "VLC": "Valencia"
}

# ============================================================
# MODELOS PYDANTIC
# ============================================================

class ValidateRequest(BaseModel):
    token: str
    user_id: Optional[str] = None

class ValidateResponse(BaseModel):
    valid: bool
    city: Optional[str] = None
    city_code: Optional[str] = None
    mission_id: Optional[str] = None
    message: str
    error: Optional[str] = None

class TokenGenerateRequest(BaseModel):
    city_code: str
    mission_id: Optional[str] = None

class TokenGenerateResponse(BaseModel):
    token: str
    url: str
    city: str
    expires_at: str

class StatsResponse(BaseModel):
    total: dict
    by_city: dict

# ============================================================
# BASE DE DATOS
# ============================================================

def init_db():
    """Inicializa la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            city_code TEXT NOT NULL,
            mission_id TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT DEFAULT 'activo',
            used_at TEXT,
            used_by TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_token ON tokens(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tokens(status)")
    
    conn.commit()
    conn.close()
    return DB_PATH

# ============================================================
# LIFESPAN (startup/shutdown)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db_path = init_db()
    print(f"Server started. Database: {db_path}")
    yield
    # Shutdown
    print("Server stopped")

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Ciudad Secreta - Token API",
    description="API para validar tokens QR dinámicos",
    version="1.0.0",
    lifespan=lifespan
)

# CORS para permitir acceso desde la app móvil
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# HELPERS
# ============================================================

def generate_token_hmac(city_code: str, mission_id: Optional[str] = None) -> dict:
    """Genera un token con HMAC-SHA256."""
    if city_code not in CITIES:
        raise ValueError(f"Ciudad inválida: {city_code}")
    
    timestamp = int(time.time())
    nonce = secrets.token_hex(8)
    data = f"{city_code}:{timestamp}:{nonce}:{mission_id or ''}"
    
    token = hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=TOKEN_EXPIRY_HOURS)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tokens (token, city_code, mission_id, created_at, expires_at, status)
        VALUES (?, ?, ?, ?, ?, 'activo')
    """, (token, city_code, mission_id, created_at.isoformat(), expires_at.isoformat()))
    conn.commit()
    conn.close()
    
    return {
        "token": token,
        "url": f"https://cs.{city_code.lower()}/{token}",
        "city": CITIES[city_code],
        "city_code": city_code,
        "mission_id": mission_id,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat()
    }

def validate_token_db(token: str, mark_used: bool = False, user_id: Optional[str] = None) -> dict:
    """Valida un token contra la base de datos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tokens WHERE token = ?", (token,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {"valid": False, "error": "TOKEN_NOT_FOUND", "message": "El token no existe"}
    
    data = dict(row)
    
    # Verificar estado
    if data["status"] == "usado":
        conn.close()
        return {
            "valid": False,
            "error": "TOKEN_ALREADY_USED",
            "message": "Este token ya ha sido utilizado",
            "used_at": data["used_at"],
            "used_by": data["used_by"]
        }
    
    # Verificar caducidad
    expires_at = datetime.fromisoformat(data["expires_at"])
    if datetime.now() > expires_at:
        cursor.execute("UPDATE tokens SET status = 'expirado' WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return {
            "valid": False,
            "error": "TOKEN_EXPIRED",
            "message": f"El token expiró el {expires_at.strftime('%d/%m/%Y %H:%M')}"
        }
    
    # Válido
    if mark_used:
        used_at = datetime.now().isoformat()
        cursor.execute(
            "UPDATE tokens SET status = 'usado', used_at = ?, used_by = ? WHERE token = ?",
            (used_at, user_id, token)
        )
        conn.commit()
        data["status"] = "usado"
        data["used_at"] = used_at
        data["used_by"] = user_id
    
    conn.close()
    
    return {
        "valid": True,
        "city": CITIES.get(data["city_code"], data["city_code"]),
        "city_code": data["city_code"],
        "mission_id": data["mission_id"],
        "created_at": data["created_at"],
        "expires_at": data["expires_at"],
        "status": data["status"],
        "message": "Token valido. Misión completada!"
    }

def get_stats_db() -> dict:
    """Obtiene estadísticas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    for code, name in CITIES.items():
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM tokens 
            WHERE city_code = ?
            GROUP BY status
        """, (code,))
        city_stats = {"activo": 0, "usado": 0, "expirado": 0}
        for row in cursor.fetchall():
            city_stats[row[0]] = row[1]
        city_stats["total"] = sum(city_stats.values())
        stats[name] = city_stats
    
    conn.close()
    return {"by_city": stats}

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "Ciudad Secreta Token API", "version": "1.0.0"}

@app.get("/health")
async def health():
    """Health check detallado."""
    return {
        "status": "healthy",
        "database": str(DB_PATH),
        "db_exists": DB_PATH.exists()
    }

# --- Validación ---

@app.get("/api/v1/validate/{token}", response_model=ValidateResponse)
async def validate_token_get(token: str):
    """
    Valida un token (GET).
    
    Ejemplo: GET /api/v1/validate/d2b635361a9ef669
    """
    result = validate_token_db(token, mark_used=False)
    return ValidateResponse(**result)

@app.post("/api/v1/scan", response_model=ValidateResponse)
async def scan_token(request: ValidateRequest):
    """
    Escanea un token y lo marca como usado.
    
    POST /api/v1/scan
    Body: {"token": "d2b635361a9ef669", "user_id": "usuario_123"}
    """
    result = validate_token_db(request.token, mark_used=True, user_id=request.user_id)
    return ValidateResponse(**result)

# --- Generación ---

@app.post("/api/v1/generate", response_model=TokenGenerateResponse)
async def generate_token(request: TokenGenerateRequest):
    """
    Genera un nuevo token.
    
    POST /api/v1/generate
    Body: {"city_code": "MAD", "mission_id": "mision_001"}
    """
    try:
        result = generate_token_hmac(request.city_code, request.mission_id)
        return TokenGenerateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/generate/batch")
async def generate_batch(city_code: str, count: int = 10):
    """
    Genera múltiples tokens.
    
    POST /api/v1/generate/batch?city_code=MAD&count=10
    """
    tokens = []
    for i in range(count):
        t = generate_token_hmac(city_code)
        tokens.append(t)
    return {"tokens": tokens, "count": count, "city": CITIES.get(city_code, city_code)}

# --- Estadísticas ---

@app.get("/api/v1/stats", response_model=StatsResponse)
async def stats():
    """Obtiene estadísticas de tokens."""
    return get_stats_db()

# --- URLs dinámicas ---

@app.get("/go/{token}")
async def redirect_to_mission(token: str):
    """
    Redirige desde URL corta QR a la misión.
    
    Ejemplo: /go/d2b635361a9ef669
    """
    result = validate_token_db(token, mark_used=False)
    
    if not result["valid"]:
        return JSONResponse(
            status_code=404,
            content={
                "error": result["error"],
                "message": result["message"]
            }
        )
    
    # En producción, redirigir a la app
    # return RedirectResponse(url=f"ciudadsecreta://mission/{token}")
    
    # Por ahora, devolver JSON
    return JSONResponse(content={
        "success": True,
        "city": result["city"],
        "city_code": result["city_code"],
        "mission_id": result.get("mission_id"),
        "message": "Escanea este codigo en la app para completar la mission"
    })

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
