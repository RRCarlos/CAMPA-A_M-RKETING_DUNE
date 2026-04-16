"""
Ciudad Secreta - Sistema de Tokens QR Dinámicos
===============================================
Genera tokens seguros con HMAC-SHA256, caducidad 24h y uso único.
"""

import hmac
import hashlib
import time
import secrets
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv no instalado, continuar sin él

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Clave secreta - debe ser la misma que en server.py y en .env
SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY:
    print("=" * 60)
    print("ADVERTENCIA: SECRET_KEY no encontrada en variables de entorno")
    print("Se generara una nueva clave (tokens existentes no seran validos)")
    print("=" * 60)
    SECRET_KEY = secrets.token_hex(32)
    print(f"Nueva SECRET_KEY: {SECRET_KEY}")
    print("COPIAR ESTA CLAVE AL ARCHIVO .env para uso futuro")
    print("=" * 60)

DB_PATH = Path(__file__).parent / "tokens.db"
TOKEN_EXPIRY_HOURS = 24

# Ciudades válidas
CITIES = {
    "MAD": "Madrid",
    "BCN": "Barcelona", 
    "VLC": "Valencia"
}


class TokenStatus(Enum):
    ACTIVO = "activo"
    USADO = "usado"
    EXPIRADO = "expirado"


# ============================================================
# ESQUEMA DE BASE DE DATOS
# ============================================================

def init_db():
    """Inicializa la base de datos SQLite."""
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
            used_by TEXT,
            metadata TEXT
        )
    """)
    
    # Índice para búsqueda rápida
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token ON tokens(token)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_status_expires ON tokens(status, expires_at)
    """)
    
    conn.commit()
    conn.close()
    print(f"[OK] Base de datos inicializada: {DB_PATH}")


# ============================================================
# GENERACIÓN DE TOKENS
# ============================================================

def generate_token(city_code: str, mission_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Genera un token dinámico seguro.
    
    El token se genera con HMAC-SHA256 usando:
    - city_code: código de ciudad (MAD, BCN, VLC)
    - timestamp: hora actual (para caducidad)
    - nonce: número aleatorio (para unicidad)
    - mission_id: identificador de misión (opcional)
    
    Returns:
        Dict con token, url, y metadatos
    """
    if city_code not in CITIES:
        raise ValueError(f"Ciudad inválida: {city_code}. Válidos: {list(CITIES.keys())}")
    
    # Timestamp actual (unix)
    timestamp = int(time.time())
    
    # Nonce aleatorio
    nonce = secrets.token_hex(8)
    
    # Datos para HMAC
    data = f"{city_code}:{timestamp}:{nonce}:{mission_id or ''}"
    
    # Generar HMAC-SHA256
    token = hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:16]  # Tomar primeros 16 chars
    
    # Caducidad
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=TOKEN_EXPIRY_HOURS)
    
    # Guardar en base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tokens (token, city_code, mission_id, created_at, expires_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        token,
        city_code,
        mission_id,
        created_at.isoformat(),
        expires_at.isoformat(),
        TokenStatus.ACTIVO.value
    ))
    
    conn.commit()
    conn.close()
    
    # URL completa
    prefix = f"cs.{city_code.lower()}"
    url = f"https://{prefix}/{token}"
    
    return {
        "token": token,
        "url": url,
        "city": CITIES[city_code],
        "city_code": city_code,
        "mission_id": mission_id,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "expires_in_hours": TOKEN_EXPIRY_HOURS,
        "status": TokenStatus.ACTIVO.value
    }


def generate_batch(city_code: str, count: int, mission_prefix: Optional[str] = None) -> list:
    """Genera múltiples tokens para una ciudad."""
    tokens = []
    for i in range(count):
        mission_id = f"{mission_prefix or city_code}-{i+1:03d}" if mission_prefix else None
        token_data = generate_token(city_code, mission_id)
        tokens.append(token_data)
    return tokens


# ============================================================
# VALIDACIÓN DE TOKENS
# ============================================================

def validate_token(token: str, mark_as_used: bool = False, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Valida un token.
    
    Checks:
    1. El token existe
    2. No ha sido usado
    3. No ha expirado
    
    Args:
        token: El token a validar
        mark_as_used: Si True, marca el token como usado tras validarlo
        user_id: ID del usuario que usa el token (opcional)
    
    Returns:
        Dict con resultado de validación
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar token
    cursor.execute("SELECT * FROM tokens WHERE token = ?", (token,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {
            "valid": False,
            "error": "TOKEN_NOT_FOUND",
            "message": "El token no existe"
        }
    
    token_data = dict(row)
    
    # Verificar estado
    if token_data["status"] == TokenStatus.USADO.value:
        conn.close()
        return {
            "valid": False,
            "error": "TOKEN_ALREADY_USED",
            "message": "Este token ya ha sido utilizado",
            "used_at": token_data["used_at"],
            "used_by": token_data["used_by"]
        }
    
    # Verificar caducidad
    expires_at = datetime.fromisoformat(token_data["expires_at"])
    if datetime.now() > expires_at:
        # Marcar como expirado
        cursor.execute(
            "UPDATE tokens SET status = ? WHERE token = ?",
            (TokenStatus.EXPIRADO.value, token)
        )
        conn.commit()
        conn.close()
        return {
            "valid": False,
            "error": "TOKEN_EXPIRED",
            "message": f"El token expiró el {expires_at.strftime('%d/%m/%Y %H:%M')}"
        }
    
    # Token válido
    if mark_as_used:
        used_at = datetime.now().isoformat()
        cursor.execute(
            "UPDATE tokens SET status = ?, used_at = ?, used_by = ? WHERE token = ?",
            (TokenStatus.USADO.value, used_at, user_id, token)
        )
        conn.commit()
        
        token_data["status"] = TokenStatus.USADO.value
        token_data["used_at"] = used_at
        token_data["used_by"] = user_id
    
    conn.close()
    
    return {
        "valid": True,
        "token": token,
        "city": CITIES.get(token_data["city_code"], token_data["city_code"]),
        "city_code": token_data["city_code"],
        "mission_id": token_data["mission_id"],
        "created_at": token_data["created_at"],
        "expires_at": token_data["expires_at"],
        "status": token_data["status"],
        "message": "Token válido. ¡Misión completada!"
    }


# ============================================================
# UTILIDADES
# ============================================================

def get_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de tokens."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    for city_code in CITIES.keys():
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM tokens 
            WHERE city_code = ?
            GROUP BY status
        """, (city_code,))
        
        city_stats = {"activo": 0, "usado": 0, "expirado": 0}
        for row in cursor.fetchall():
            city_stats[row[0]] = row[1]
        city_stats["total"] = sum(city_stats.values())
        stats[CITIES[city_code]] = city_stats
    
    # Totales
    stats["total"] = {k: sum(s[k] for s in stats.values() if isinstance(s, dict)) for k in ["activo", "usado", "expirado", "total"]}
    
    conn.close()
    return stats


def cleanup_expired():
    """Marca tokens expirados como tales (limpieza)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE tokens 
        SET status = ? 
        WHERE status = ? AND expires_at < ?
    """, (
        TokenStatus.EXPIRADO.value,
        TokenStatus.ACTIVO.value,
        datetime.now().isoformat()
    ))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted > 0:
        print(f"[OK] {deleted} tokens marcados como expirados")
    
    return deleted


def export_tokens(city_code: Optional[str] = None, status: Optional[str] = None) -> list:
    """Exporta tokens a lista."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM tokens WHERE 1=1"
    params = []
    
    if city_code:
        query += " AND city_code = ?"
        params.append(city_code)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def export_qr_data(city_code: str, count: int) -> list:
    """Genera y exporta tokens listos para QR con URLs completas."""
    cleanup_expired()
    tokens = generate_batch(city_code, count)
    
    return [{
        "num": i + 1,
        "city": CITIES[city_code],
        "city_code": city_code,
        "token": t["token"],
        "url": t["url"],
        "mission_id": t["mission_id"],
        "expires_at": t["expires_at"]
    } for i, t in enumerate(tokens)]


# ============================================================
# CLI INTERFAZ
# ============================================================

def print_token(t: Dict):
    """Imprime un token formateado."""
    print(f"\n{'='*50}")
    print(f"Ciudad:     {t['city']} ({t['city_code']})")
    print(f"Misión:     {t.get('mission_id', 'N/A')}")
    print(f"Token:      {t['token']}")
    print(f"URL:        {t['url']}")
    print(f"Creado:     {t['created_at']}")
    print(f"Expira:     {t['expires_at']}")
    print(f"Estado:     {t['status'].upper()}")
    print(f"{'='*50}")


def print_stats(stats: Dict):
    """Imprime estadísticas formateadas."""
    print("\n" + "="*60)
    print("ESTADÍSTICAS DE TOKENS")
    print("="*60)
    
    for city, data in stats.items():
        if city == "total":
            continue
        print(f"\n{city}:")
        print(f"  Activos:   {data['activo']}")
        print(f"  Usados:    {data['usado']}")
        print(f"  Expirados: {data['expirado']}")
        print(f"  Total:     {data['total']}")
    
    print(f"\n{'='*60}")
    print("TOTALES:")
    print(f"  Activos:   {stats['total']['activo']}")
    print(f"  Usados:    {stats['total']['usado']}")
    print(f"  Expirados: {stats['total']['expirado']}")
    print(f"  TOTAL:     {stats['total']['total']}")
    print("="*60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sistema de Tokens QR - Ciudad Secreta")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # init
    subparsers.add_parser("init", help="Inicializar base de datos")
    
    # generate
    gen_parser = subparsers.add_parser("generate", help="Generar tokens")
    gen_parser.add_argument("-c", "--city", required=True, choices=["MAD", "BCN", "VLC"], help="Ciudad")
    gen_parser.add_argument("-n", "--number", type=int, default=1, help="Cantidad de tokens")
    gen_parser.add_argument("-p", "--prefix", help="Prefijo para mission_id")
    
    # validate
    val_parser = subparsers.add_parser("validate", help="Validar un token")
    val_parser.add_argument("token", help="Token a validar")
    val_parser.add_argument("--use", action="store_true", help="Marcar como usado")
    val_parser.add_argument("--user", help="ID del usuario")
    
    # stats
    subparsers.add_parser("stats", help="Ver estadísticas")
    
    # cleanup
    subparsers.add_parser("cleanup", help="Limpiar tokens expirados")
    
    # export
    exp_parser = subparsers.add_parser("export", help="Exportar tokens")
    exp_parser.add_argument("--city", choices=["MAD", "BCN", "VLC"], help="Filtrar por ciudad")
    exp_parser.add_argument("--status", help="Filtrar por estado")
    
    # batch-generate
    batch_parser = subparsers.add_parser("batch", help="Generar lote completo para campaña")
    batch_parser.add_argument("-n", "--per-city", type=int, default=10, help="Tokens por ciudad")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        exit(0)
    
    # Inicializar DB siempre
    init_db()
    
    if args.command == "init":
        print("Base de datos ya inicializada")
        
    elif args.command == "generate":
        tokens = generate_batch(args.city, args.number, args.prefix)
        for t in tokens:
            print_token(t)
        print(f"\n[OK] Generados {len(tokens)} tokens para {CITIES[args.city]}")
        
    elif args.command == "validate":
        result = validate_token(args.token, mark_as_used=args.use, user_id=args.user)
        if result["valid"]:
            print(f"[OK] Token VALIDO")
            print(f"     Ciudad: {result['city']}")
            print(f"     Misión: {result.get('mission_id', 'N/A')}")
            if args.use:
                print(f"     Marcado como USADO")
        else:
            print(f"[ERROR] Token INVÁLIDO: {result['error']}")
            print(f"        {result['message']}")
            
    elif args.command == "stats":
        print_stats(get_stats())
        
    elif args.command == "cleanup":
        deleted = cleanup_expired()
        print(f"[OK] Limpieza completada. {deleted} tokens expirados marcados.")
        
    elif args.command == "export":
        tokens = export_tokens(args.city, args.status)
        for t in tokens:
            print(f"{t['token']} | {t['city_code']} | {t['status']} | {t['expires_at']}")
        print(f"\nTotal: {len(tokens)} tokens")
        
    elif args.command == "batch":
        print("="*60)
        print("GENERANDO LOTE COMPLETO PARA CAMPAÑA")
        print("="*60)
        
        all_tokens = []
        for city_code in CITIES.keys():
            tokens = export_qr_data(city_code, args.per_city)
            all_tokens.extend(tokens)
            
        # Guardar en JSON
        output_file = Path(__file__).parent / "tokens_batch.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_tokens, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Generados {len(all_tokens)} tokens en {output_file}")
        print("\nResumen:")
        for city_code in CITIES.keys():
            count = len([t for t in all_tokens if t["city_code"] == city_code])
            print(f"  {CITIES[city_code]}: {count} tokens")
