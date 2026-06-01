# -*- coding: utf-8 -*-
import mysql.connector.pooling
import os

_pool = None

DEFAULT_DB_HOST = "gateway01.us-east-1.prod.aws.tidbcloud.com"
DEFAULT_DB_PORT = 4000


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Variable de entorno requerida no configurada: {name}")
    return value


def _create_pool():
    global _pool
    _pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="tuniche_pool",
        pool_size=5,
        host=os.environ.get("DB_HOST", DEFAULT_DB_HOST),
        port=int(os.environ.get("DB_PORT", DEFAULT_DB_PORT)),
        user=_required_env("DB_USER"),
        password=_required_env("DB_PASSWORD"),
        ssl_verify_cert=False,
        ssl_verify_identity=False,
        use_pure=True,
        connect_timeout=8,
    )
    return _pool


def get_connection(planta: str):
    """Retorna una conexion del pool, apuntando a la BD de la planta correcta."""
    global _pool
    if _pool is None:
        _create_pool()

    db_name = (
        os.environ.get("DB_NAME_TUNICHE", "bodega_tuniche_real")
        if planta == "TUNICHE"
        else os.environ.get("DB_NAME_PUQUILLAY", "bodega_puquillay_real")
    )

    conn = _pool.get_connection()
    cur = conn.cursor()
    cur.execute(f"USE `{db_name}`")
    cur.close()
    return conn


def ensure_cierres_table_exists():
    """Crea la tabla cierres_turno en ambas bases de datos si no existe al iniciar."""
    for planta in ("TUNICHE", "PUQUILLAY"):
        conn = None
        try:
            conn = get_connection(planta)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cierres_turno (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    planta VARCHAR(32) NOT NULL,
                    tipo_turno VARCHAR(16) NOT NULL,
                    fecha_operativa DATE NOT NULL,
                    desde DATETIME NOT NULL,
                    hasta DATETIME NOT NULL,
                    responsable VARCHAR(100) NOT NULL,
                    hora_cierre DATETIME NOT NULL,
                    total INT NOT NULL DEFAULT 0,
                    salidas INT NOT NULL DEFAULT 0,
                    devoluciones INT NOT NULL DEFAULT 0,
                    pendientes INT NOT NULL DEFAULT 0,
                    trabajadores_pendientes INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_cierre_turno_operativo (planta, tipo_turno, fecha_operativa)
                )
            """)
            conn.commit()
            cur.close()
        except Exception as e:
            import logging
            logging.getLogger("flask.app").error(f"Error al asegurar la tabla cierres_turno en la base de datos de {planta}: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()
