# -*- coding: utf-8 -*-
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth import get_current_modulo, get_current_planta, get_current_user, login_required
from db import get_connection

embalaje_bp = Blueprint("embalaje", __name__, url_prefix="/api/embalaje")


def _require_embalaje():
    if get_current_modulo() != "EMBALAJE":
        return jsonify({"success": False, "message": "Este acceso es solo para el modulo Embalaje."}), 403
    return None


def _estado_por_ubicacion(ubicacion: str) -> str:
    ubicacion = str(ubicacion or "").strip().upper()
    if ubicacion.startswith("PACKING"):
        return "EN PACKING"
    if ubicacion.startswith("ALTILLO"):
        return "EN ALTILLO"
    if ubicacion.startswith("BODEGA"):
        return "EN BODEGA"
    return "ARMADO"


def _serializar_existencia(row):
    if not row:
        return None
    return {
        "id": row[0],
        "correlativo": row[1],
        "codigo_material": row[2],
        "descripcion": row[3],
        "lote": row[4],
        "cantidad_armada": row[5],
        "merma": row[6],
        "cantidad_neta": row[7],
        "bodega_actual": row[8],
        "estado": row[9],
        "fecha_armado": row[10],
        "usuario_armado": row[11],
        "proveedor_origen": row[12],
        "guia_recepcion": row[13],
        "guia_proveedor": row[14],
        "qr_payload": row[15],
        "ultimo_movimiento": row[16],
        "numero_pallet": row[17] if len(row) > 17 else "",
        "correlativo_inicio": row[18] if len(row) > 18 else "",
        "orden_compra": row[19] if len(row) > 19 else "",
        "documento_recepcion": row[20] if len(row) > 20 else "",
        "maquina": row[21] if len(row) > 21 else "",
        "turno": row[22] if len(row) > 22 else "",
    }


@embalaje_bp.route("/resumen", methods=["GET"])
@login_required
def resumen():
    if (resp := _require_embalaje()) is not None:
        return resp

    planta = get_current_planta()
    texto = request.args.get("texto", "").strip()
    ubicacion = request.args.get("ubicacion", "Todas").strip()
    estado = request.args.get("estado", "Todos").strip()
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()

    query = """
        SELECT
            COUNT(*) AS total_armado,
            IFNULL(SUM(e.cantidad_neta), 0) AS stock_actual,
            IFNULL(SUM(CASE WHEN UPPER(e.bodega_actual) LIKE 'PACKING%%' THEN e.cantidad_neta ELSE 0 END), 0) AS en_packing,
            IFNULL(SUM(CASE WHEN UPPER(e.bodega_actual) LIKE 'ALTILLO%%' THEN e.cantidad_neta ELSE 0 END), 0) AS en_altillo,
            IFNULL(SUM(e.merma), 0) AS mermas
        FROM embalaje_existencias e
        WHERE e.sucursal = %s
    """
    params = [planta]
    if texto:
        like_val = f"%{texto}%"
        query += """
            AND (
                LOWER(e.correlativo) LIKE LOWER(%s)
                OR LOWER(e.codigo_material) LIKE LOWER(%s)
                OR LOWER(e.descripcion) LIKE LOWER(%s)
                OR LOWER(e.lote) LIKE LOWER(%s)
                OR LOWER(e.qr_payload) LIKE LOWER(%s)
            )
        """
        params.extend([like_val] * 5)
    if ubicacion != "Todas":
        query += " AND e.bodega_actual = %s"
        params.append(ubicacion)
    if estado != "Todos":
        query += " AND e.estado = %s"
        params.append(estado)
    if desde:
        query += " AND DATE(e.fecha_armado) >= %s"
        params.append(desde)
    if hasta:
        query += " AND DATE(e.fecha_armado) <= %s"
        params.append(hasta)

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        fila = cur.fetchone() or (0, 0, 0, 0, 0)

        query_traslado = """
            SELECT IFNULL(SUM(m.cantidad), 0)
            FROM embalaje_movimientos m
            INNER JOIN embalaje_existencias e ON e.id = m.existencia_id
            WHERE m.tipo_movimiento = 'TRASLADO'
              AND DATE(m.fecha_hora) = CURDATE()
              AND e.sucursal = %s
        """
        params_traslado = [planta]
        if texto:
            query_traslado += """
                AND (
                    LOWER(e.correlativo) LIKE LOWER(%s)
                    OR LOWER(e.codigo_material) LIKE LOWER(%s)
                    OR LOWER(e.descripcion) LIKE LOWER(%s)
                    OR LOWER(e.lote) LIKE LOWER(%s)
                    OR LOWER(e.qr_payload) LIKE LOWER(%s)
                )
            """
            params_traslado.extend([like_val] * 5)
        if ubicacion != "Todas":
            query_traslado += " AND e.bodega_actual = %s"
            params_traslado.append(ubicacion)
        if estado != "Todos":
            query_traslado += " AND e.estado = %s"
            params_traslado.append(estado)
        if desde:
            query_traslado += " AND DATE(e.fecha_armado) >= %s"
            params_traslado.append(desde)
        if hasta:
            query_traslado += " AND DATE(e.fecha_armado) <= %s"
            params_traslado.append(hasta)

        cur.execute(query_traslado, tuple(params_traslado))
        fila_traslado = cur.fetchone() or (0,)
        cur.close()
    finally:
        if conn:
            conn.close()

    return jsonify({
        "success": True,
        "resumen": {
            "total_armado": int(fila[0] or 0),
            "stock_actual": int(fila[1] or 0),
            "en_packing": int(fila[2] or 0),
            "en_altillo": int(fila[3] or 0),
            "trasladado_hoy": int(fila_traslado[0] or 0),
            "mermas": int(fila[4] or 0),
        },
    })


@embalaje_bp.route("/existencias", methods=["GET"])
@login_required
def existencias():
    if (resp := _require_embalaje()) is not None:
        return resp

    planta = get_current_planta()
    texto = request.args.get("texto", "").strip()
    ubicacion = request.args.get("ubicacion", "Todas").strip()
    estado = request.args.get("estado", "Todos").strip()
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()

    query = """
        SELECT
            e.id,
            e.correlativo,
            e.codigo_material,
            e.descripcion,
            e.lote,
            e.cantidad_armada,
            e.merma,
            e.cantidad_neta,
            e.bodega_actual,
            e.estado,
            DATE_FORMAT(e.fecha_armado, '%%d-%%m-%%Y %%H:%%i:%%S'),
            e.usuario_armado,
            IFNULL(e.proveedor_origen, ''),
            IFNULL(e.guia_recepcion, ''),
            IFNULL(e.guia_proveedor, ''),
            e.qr_payload,
            IFNULL(DATE_FORMAT(m.fecha_hora, '%%d-%%m-%%Y %%H:%%i:%%S'), ''),
            IFNULL(e.numero_pallet, ''),
            IFNULL(e.correlativo_inicio, ''),
            IFNULL(e.orden_compra, ''),
            IFNULL(e.documento_recepcion, ''),
            IFNULL(e.maquina, ''),
            IFNULL(e.turno, '')
        FROM embalaje_existencias e
        LEFT JOIN (
            SELECT em1.*
            FROM embalaje_movimientos em1
            INNER JOIN (
                SELECT existencia_id, MAX(id) AS max_id
                FROM embalaje_movimientos
                GROUP BY existencia_id
            ) em2 ON em2.max_id = em1.id
        ) m ON m.existencia_id = e.id
        WHERE e.sucursal = %s
    """
    params = [planta]
    if texto:
        like_val = f"%{texto}%"
        query += """
            AND (
                LOWER(e.correlativo) LIKE LOWER(%s)
                OR LOWER(e.codigo_material) LIKE LOWER(%s)
                OR LOWER(e.descripcion) LIKE LOWER(%s)
                OR LOWER(e.lote) LIKE LOWER(%s)
                OR LOWER(e.qr_payload) LIKE LOWER(%s)
            )
        """
        params.extend([like_val] * 5)
    if ubicacion != "Todas":
        query += " AND e.bodega_actual = %s"
        params.append(ubicacion)
    if estado != "Todos":
        query += " AND e.estado = %s"
        params.append(estado)
    if desde:
        query += " AND DATE(e.fecha_armado) >= %s"
        params.append(desde)
    if hasta:
        query += " AND DATE(e.fecha_armado) <= %s"
        params.append(hasta)
    query += " ORDER BY e.fecha_armado DESC, e.id DESC"

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        datos = [_serializar_existencia(fila) for fila in cur.fetchall()]
        cur.close()
        return jsonify({"success": True, "existencias": datos})
    finally:
        if conn:
            conn.close()


@embalaje_bp.route("/existencia", methods=["GET"])
@login_required
def existencia():
    if (resp := _require_embalaje()) is not None:
        return resp

    planta = get_current_planta()
    clave = request.args.get("clave", "").strip()
    if not clave:
        return jsonify({"success": False, "message": "Clave requerida."}), 400

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                e.id, e.correlativo, e.codigo_material, e.descripcion, e.lote,
                e.cantidad_armada, e.merma, e.cantidad_neta, e.bodega_actual,
                e.estado, DATE_FORMAT(e.fecha_armado, '%%d-%%m-%%Y %%H:%%i:%%S'),
                e.usuario_armado, IFNULL(e.proveedor_origen, ''),
                IFNULL(e.guia_recepcion, ''), IFNULL(e.guia_proveedor, ''),
                e.qr_payload, '',
                IFNULL(e.numero_pallet, ''), IFNULL(e.correlativo_inicio, ''),
                IFNULL(e.orden_compra, ''), IFNULL(e.documento_recepcion, ''),
                IFNULL(e.maquina, ''), IFNULL(e.turno, '')
            FROM embalaje_existencias e
            WHERE e.sucursal = %s AND (e.qr_payload = %s OR e.correlativo = %s OR e.codigo_material = %s)
            ORDER BY e.fecha_armado DESC, e.id DESC
            LIMIT 1
        """, (planta, clave, clave, clave))
        fila = cur.fetchone()
        cur.close()
        if not fila:
            return jsonify({"success": False, "message": "No se encontro la existencia."}), 404
        return jsonify({"success": True, "existencia": _serializar_existencia(fila)})
    finally:
        if conn:
            conn.close()


@embalaje_bp.route("/movimientos", methods=["GET"])
@login_required
def movimientos():
    if (resp := _require_embalaje()) is not None:
        return resp

    planta = get_current_planta()
    texto = request.args.get("texto", "").strip()
    limite = int(request.args.get("limite", 200))

    query = """
        SELECT
            DATE_FORMAT(m.fecha_hora, '%%d-%%m-%%Y %%H:%%i:%%S'),
            e.correlativo,
            m.bodega_origen,
            m.bodega_destino,
            m.cantidad,
            m.usuario,
            IFNULL(m.observacion, '')
        FROM embalaje_movimientos m
        INNER JOIN embalaje_existencias e ON e.id = m.existencia_id
        WHERE e.sucursal = %s
    """
    params = [planta]
    if texto:
        like_val = f"%{texto}%"
        query += """
            AND (
                LOWER(e.correlativo) LIKE LOWER(%s)
                OR LOWER(e.codigo_material) LIKE LOWER(%s)
                OR LOWER(e.descripcion) LIKE LOWER(%s)
                OR LOWER(m.bodega_origen) LIKE LOWER(%s)
                OR LOWER(m.bodega_destino) LIKE LOWER(%s)
            )
        """
        params.extend([like_val] * 5)
    query += " ORDER BY m.fecha_hora DESC, m.id DESC LIMIT %s"
    params.append(limite)

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        datos = cur.fetchall()
        cur.close()
        return jsonify({
            "success": True,
            "movimientos": [
                {
                    "fecha_hora": row[0],
                    "correlativo": row[1],
                    "origen": row[2],
                    "destino": row[3],
                    "cantidad": row[4],
                    "usuario": row[5],
                    "observacion": row[6],
                }
                for row in datos
            ],
        })
    finally:
        if conn:
            conn.close()


@embalaje_bp.route("/armado", methods=["POST"])
@login_required
def armado():
    if (resp := _require_embalaje()) is not None:
        return resp

    data = request.get_json() or {}
    planta = get_current_planta()
    usuario = get_current_user()
    sucursal = planta
    codigo_material = str(data.get("codigo_material") or "").strip().upper()
    descripcion = str(data.get("descripcion") or "").strip()
    lote = str(data.get("lote") or "").strip().upper()
    cantidad_armada = int(data.get("cantidad_armada") or 0)
    merma = int(data.get("merma") or 0)
    bodega_actual = str(data.get("bodega_actual") or "").strip().upper()
    proveedor_origen = str(data.get("proveedor_origen") or "").strip()
    guia_recepcion = str(data.get("guia_recepcion") or "").strip()
    guia_proveedor = str(data.get("guia_proveedor") or "").strip()
    numero_pallet = str(data.get("numero_pallet") or "").strip().upper()
    correlativo_inicio = str(data.get("correlativo_inicio") or "").strip().upper()
    orden_compra = str(data.get("orden_compra") or "").strip().upper()
    documento_recepcion = str(data.get("documento_recepcion") or "").strip().upper()
    maquina = str(data.get("maquina") or "").strip().upper()
    turno = str(data.get("turno") or "").strip().upper()
    observacion = str(data.get("observacion") or "").strip()
    medida = str(data.get("medida") or "").strip()
    unidad = str(data.get("unidad") or "UND").strip().upper() or "UND"
    correlativo = str(data.get("correlativo") or "").strip().upper()
    qr_payload = str(data.get("qr_payload") or "").strip().upper()
    fecha_armado = datetime.now()

    if not (codigo_material and descripcion and lote and bodega_actual):
        return jsonify({"success": False, "message": "Faltan campos obligatorios."}), 400
    if cantidad_armada <= 0:
        return jsonify({"success": False, "message": "La cantidad armada debe ser mayor a cero."}), 400
    if merma < 0 or merma > cantidad_armada:
        return jsonify({"success": False, "message": "La merma es invalida."}), 400

    cantidad_neta = max(cantidad_armada - merma, 0)
    if not correlativo:
        correlativo = f"EMB-{sucursal[:3]}-{datetime.now():%Y%m%d%H%M%S}"
    if not qr_payload:
        qr_payload = correlativo

    estado = _estado_por_ubicacion(bodega_actual)

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO embalaje_formatos (codigo_formato, familia, descripcion, medida, unidad, activo)
            VALUES (%s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                familia = VALUES(familia),
                descripcion = VALUES(descripcion),
                medida = VALUES(medida),
                unidad = VALUES(unidad),
                activo = 1
        """, (codigo_material, "EMBALAJE", descripcion, medida, unidad))
        cur.execute("SELECT id FROM embalaje_formatos WHERE codigo_formato = %s LIMIT 1", (codigo_material,))
        fila_formato = cur.fetchone()
        if not fila_formato:
            raise ValueError("No se pudo resolver el formato.")
        formato_id = int(fila_formato[0])
        cur.execute("SELECT 1 FROM embalaje_existencias WHERE qr_payload = %s LIMIT 1", (qr_payload,))
        if cur.fetchone():
            return jsonify({"success": False, "message": "Ya existe una existencia con ese QR."}), 409
        cur.execute("""
            INSERT INTO embalaje_existencias (
                correlativo, sucursal, formato_id, codigo_material, descripcion, medida, unidad,
                lote, cantidad_armada, merma, cantidad_neta, bodega_actual, estado, qr_payload,
                fecha_armado, usuario_armado, proveedor_origen, guia_recepcion, guia_proveedor,
                numero_pallet, correlativo_inicio, orden_compra, documento_recepcion, maquina, turno,
                observacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            correlativo, sucursal, formato_id, codigo_material, descripcion, medida, unidad,
            lote, cantidad_armada, merma, cantidad_neta, bodega_actual, estado, qr_payload,
            fecha_armado, usuario, proveedor_origen or None, guia_recepcion or None, guia_proveedor or None,
            numero_pallet or None, correlativo_inicio or None, orden_compra or None, documento_recepcion or None,
            maquina or None, turno or None, observacion or None,
        ))
        existencia_id = cur.lastrowid
        cur.execute("""
            INSERT INTO embalaje_movimientos (
                existencia_id, tipo_movimiento, bodega_origen, bodega_destino, cantidad,
                fecha_hora, usuario, observacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (existencia_id, "ARMADO", "SISTEMA", bodega_actual, cantidad_neta, fecha_armado, usuario, observacion or None))
        conn.commit()
        cur.close()
        return jsonify({
            "success": True,
            "message": f"Armado registrado correctamente. QR: {qr_payload}",
            "existencia": {
                "id": existencia_id,
                "correlativo": correlativo,
                "qr_payload": qr_payload,
                "codigo_material": codigo_material,
                "descripcion": descripcion,
                "lote": lote,
                "cantidad_armada": cantidad_armada,
                "merma": merma,
                "cantidad_neta": cantidad_neta,
                "bodega_actual": bodega_actual,
                "estado": estado,
                "numero_pallet": numero_pallet,
                "correlativo_inicio": correlativo_inicio,
                "orden_compra": orden_compra,
                "documento_recepcion": documento_recepcion,
                "maquina": maquina,
                "turno": turno,
            },
        })
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@embalaje_bp.route("/traslado", methods=["POST"])
@login_required
def traslado():
    if (resp := _require_embalaje()) is not None:
        return resp

    data = request.get_json() or {}
    planta = get_current_planta()
    usuario = get_current_user()
    clave = str(data.get("clave") or "").strip()
    destino = str(data.get("bodega_destino") or "").strip().upper()
    observacion = str(data.get("observacion") or "").strip()
    fecha_hora = datetime.now()

    if not clave or not destino:
        return jsonify({"success": False, "message": "Faltan datos del traslado."}), 400

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, correlativo, bodega_actual, cantidad_neta, qr_payload
            FROM embalaje_existencias
            WHERE sucursal = %s AND (qr_payload = %s OR correlativo = %s OR codigo_material = %s)
            ORDER BY fecha_armado DESC, id DESC
            LIMIT 1
            FOR UPDATE
        """, (planta, clave, clave, clave))
        fila = cur.fetchone()
        if not fila:
            return jsonify({"success": False, "message": "No se encontro la existencia solicitada."}), 404

        existencia_id, correlativo, bodega_actual, cantidad_neta, qr_payload = fila
        if bodega_actual == destino:
            return jsonify({"success": False, "message": "La bodega destino debe ser distinta a la actual."}), 400

        estado_nuevo = _estado_por_ubicacion(destino)
        cur.execute("UPDATE embalaje_existencias SET bodega_actual = %s, estado = %s WHERE id = %s", (destino, estado_nuevo, existencia_id))
        cur.execute("""
            INSERT INTO embalaje_movimientos (
                existencia_id, tipo_movimiento, bodega_origen, bodega_destino, cantidad,
                fecha_hora, usuario, observacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (existencia_id, "TRASLADO", bodega_actual, destino, int(cantidad_neta or 0), fecha_hora, usuario, observacion or None))
        conn.commit()
        cur.close()
        return jsonify({
            "success": True,
            "message": f"Traslado registrado correctamente. {correlativo} ahora queda en {destino}.",
            "traslado": {
                "correlativo": correlativo,
                "qr_payload": qr_payload,
                "bodega_origen": bodega_actual,
                "bodega_destino": destino,
                "cantidad": int(cantidad_neta or 0),
                "estado": estado_nuevo,
            },
        })
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()
