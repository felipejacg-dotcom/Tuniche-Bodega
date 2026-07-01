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


def ensure_embalaje_tables_exist():
    """Crea las tablas de embalaje en ambas bases de datos si no existen."""
    for planta in ("TUNICHE", "PUQUILLAY"):
        conn = None
        try:
            conn = get_connection(planta)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embalaje_formatos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    codigo_formato VARCHAR(40) NOT NULL,
                    familia VARCHAR(120) NOT NULL,
                    descripcion VARCHAR(200) NOT NULL,
                    medida VARCHAR(40) NOT NULL,
                    unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
                    activo TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_embalaje_formatos_codigo (codigo_formato),
                    KEY idx_embalaje_formatos_familia (familia),
                    KEY idx_embalaje_formatos_activo (activo)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embalaje_bodegas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sucursal VARCHAR(50) NOT NULL,
                    nombre_bodega VARCHAR(100) NOT NULL,
                    tipo_bodega VARCHAR(30) NOT NULL DEFAULT 'BODEGA',
                    activo TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_embalaje_bodegas_sucursal_nombre (sucursal, nombre_bodega),
                    KEY idx_embalaje_bodegas_sucursal (sucursal),
                    KEY idx_embalaje_bodegas_activo (activo)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embalaje_existencias (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    correlativo VARCHAR(30) NOT NULL,
                    sucursal VARCHAR(50) NOT NULL,
                    formato_id INT NOT NULL,
                    codigo_material VARCHAR(40) NOT NULL,
                    descripcion VARCHAR(200) NOT NULL,
                    medida VARCHAR(40) NOT NULL,
                    unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
                    lote VARCHAR(80) NOT NULL,
                    cantidad_armada INT NOT NULL DEFAULT 0,
                    merma INT NOT NULL DEFAULT 0,
                    cantidad_neta INT NOT NULL DEFAULT 0,
                    bodega_actual VARCHAR(100) NOT NULL,
                    estado VARCHAR(20) NOT NULL DEFAULT 'ARMADO',
                    qr_payload VARCHAR(255) NOT NULL,
                    fecha_armado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    usuario_armado VARCHAR(100) NOT NULL,
                    proveedor_origen VARCHAR(150) NULL,
                    guia_recepcion VARCHAR(80) NULL,
                    guia_proveedor VARCHAR(80) NULL,
                    observacion VARCHAR(255) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_embalaje_existencias_formato
                        FOREIGN KEY (formato_id) REFERENCES embalaje_formatos(id),
                    UNIQUE KEY uq_embalaje_existencias_correlativo (correlativo),
                    UNIQUE KEY uq_embalaje_existencias_qr (qr_payload),
                    KEY idx_embalaje_existencias_sucursal (sucursal),
                    KEY idx_embalaje_existencias_codigo (codigo_material),
                    KEY idx_embalaje_existencias_lote (lote),
                    KEY idx_embalaje_existencias_bodega (bodega_actual),
                    KEY idx_embalaje_existencias_estado (estado),
                    KEY idx_embalaje_existencias_fecha (fecha_armado)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embalaje_movimientos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    existencia_id INT NOT NULL,
                    tipo_movimiento VARCHAR(20) NOT NULL,
                    bodega_origen VARCHAR(100) NOT NULL,
                    bodega_destino VARCHAR(100) NOT NULL,
                    cantidad INT NOT NULL DEFAULT 0,
                    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    usuario VARCHAR(100) NOT NULL,
                    observacion VARCHAR(255) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_embalaje_movimientos_existencia
                        FOREIGN KEY (existencia_id) REFERENCES embalaje_existencias(id) ON DELETE CASCADE,
                    KEY idx_embalaje_movimientos_existencia (existencia_id),
                    KEY idx_embalaje_movimientos_tipo (tipo_movimiento),
                    KEY idx_embalaje_movimientos_fecha (fecha_hora),
                    KEY idx_embalaje_movimientos_origen (bodega_origen),
                    KEY idx_embalaje_movimientos_destino (bodega_destino)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embalaje_impresiones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    existencia_id INT NOT NULL,
                    usuario VARCHAR(100) NOT NULL,
                    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    tipo_impresion VARCHAR(20) NOT NULL DEFAULT 'PDF',
                    copias INT NOT NULL DEFAULT 1,
                    observacion VARCHAR(255) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_embalaje_impresiones_existencia
                        FOREIGN KEY (existencia_id) REFERENCES embalaje_existencias(id) ON DELETE CASCADE,
                    KEY idx_embalaje_impresiones_existencia (existencia_id),
                    KEY idx_embalaje_impresiones_fecha (fecha_hora),
                    KEY idx_embalaje_impresiones_usuario (usuario)
                )
            """)
            for sucursal in ("GRANEROS", "PUQUILLAY"):
                for tipo_bodega, nombre_bodega in (
                    ("PACKING", f"PACKING {sucursal}"),
                    ("ALTILLO", f"ALTILLO {sucursal}"),
                    ("BODEGA", f"BODEGA {sucursal}"),
                ):
                    cur.execute(
                        """
                        INSERT IGNORE INTO embalaje_bodegas (sucursal, nombre_bodega, tipo_bodega)
                        VALUES (%s, %s, %s)
                        """,
                        (sucursal, nombre_bodega, tipo_bodega),
                    )
            conn.commit()
            cur.close()
        except Exception as e:
            import logging
            logging.getLogger("flask.app").error(f"Error al asegurar tablas de embalaje en {planta}: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()
