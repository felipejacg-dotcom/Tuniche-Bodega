# -*- coding: utf-8 -*-
import unittest
import os
import json
import sys
from unittest.mock import patch, MagicMock

# Asegurar que se importe desde la ruta raíz del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SECRET_KEY"] = "test-secret-key-12345"
os.environ["LOGIN_USERS"] = "admin:admin123,bodega:123456"
# Variables de entorno de base de datos ficticias para evitar fallos de pool en pruebas
os.environ["DB_USER"] = "test_user"
os.environ["DB_PASSWORD"] = "test_password"

from app import app

class FlaskTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True

    def test_login_successful(self):
        response = self.app.post('/api/login', json={
            "username": "admin",
            "password": "admin123",
            "planta": "TUNICHE"
        })
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["user"], "admin")

    def test_login_failed(self):
        response = self.app.post('/api/login', json={
            "username": "admin",
            "password": "wrongpassword",
            "planta": "TUNICHE"
        })
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 401)
        self.assertFalse(data["success"])

    def test_login_restringe_usuario_a_puquillay(self):
        with patch.dict(os.environ, {
            "LOGIN_USERS": "Cristina Lopez:tuniche2026",
            "LOGIN_USER_PLANTAS": "Cristina Lopez:PUQUILLAY",
        }):
            response = self.app.post('/api/login', json={
                "username": "Cristina Lopez",
                "password": "tuniche2026",
                "planta": "TUNICHE"
            })
            data = json.loads(response.data)
            self.assertEqual(response.status_code, 401)
            self.assertFalse(data["success"])

            response = self.app.post('/api/login', json={
                "username": "Cristina Lopez",
                "password": "tuniche2026",
                "planta": "PUQUILLAY"
            })
            data = json.loads(response.data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(data["success"])
            self.assertEqual(data["planta"], "PUQUILLAY")

    def test_me_unauthorized(self):
        response = self.app.get('/api/me')
        self.assertEqual(response.status_code, 401)

    def test_me_authorized(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'
        response = self.app.get('/api/me')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["user"], "admin")

    def test_cierre_invalido_rango_fecha(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'
        # Caso Desde >= Hasta
        response = self.app.get('/api/cierre_turno?tipo_turno=dia&desde=2026-05-28T12:00&hasta=2026-05-28T10:00')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("Desde debe ser anterior a Hasta", data["message"])

    def test_cierre_invalido_rango_excesivo(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'
        # Caso rango > 24 horas
        response = self.app.get('/api/cierre_turno?tipo_turno=dia&desde=2026-05-28T10:00&hasta=2026-05-29T12:00')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("no puede superar 24 horas", data["message"])

    @patch('routes.stock_routes.get_connection')
    def test_cierre_dia_noche(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Simular respuestas SQL para múltiples llamadas en el mismo test
        mock_cur.fetchall.return_value = []
        mock_cur.fetchone.return_value = None

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'
            
        # Probar Turno Día
        response = self.app.get('/api/cierre_turno?tipo_turno=dia&desde=2026-05-28T08:00&hasta=2026-05-28T20:00')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["turno"], "Día")
        
        # Probar Turno Noche
        response = self.app.get('/api/cierre_turno?tipo_turno=noche&desde=2026-05-28T20:00&hasta=2026-05-29T08:00')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["turno"], "Noche")

    @patch('routes.stock_routes.get_connection')
    def test_cierre_preview_responsable_sin_stock_critico(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        mock_cur.fetchone.return_value = None

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.get('/api/cierre_turno?tipo_turno=dia&desde=2026-05-28T08:00&hasta=2026-05-28T20:00')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["responsable"], "admin")
        self.assertFalse(data["cerrado"])
        self.assertNotIn("stock_critico", data)
        self.assertNotIn("stock_critico", data["kpi"])

    @patch('routes.stock_routes.get_connection')
    def test_cierre_preview_includes_devoluciones(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [],
            [
                {
                    "id": 5,
                    "rut": "12.345.678-9",
                    "trabajador": "Juan Perez",
                    "area": "BODEGA",
                    "articulo": "Casco [Única]",
                    "hora_evento": "2026-05-28 14:30:00",
                    "evento": "DEVOLUCION"
                }
            ],
            []
        ]
        mock_cur.fetchone.return_value = None

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.get('/api/cierre_turno?tipo_turno=dia&desde=2026-05-28T08:00&hasta=2026-05-28T20:00')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertIn("devoluciones", data)
        self.assertEqual(len(data["devoluciones"]), 1)
        self.assertEqual(data["devoluciones"][0]["trabajador"], "Juan Perez")
        self.assertEqual(len(data["devoluciones"][0]["articulos"]), 1)
        self.assertEqual(data["devoluciones"][0]["articulos"][0]["articulo"], "Casco [Única]")

    @patch('routes.stock_routes.get_connection')
    def test_confirmar_cierre_y_bloquear_repetido(self, mock_get_conn):
        cierre_row = {
            "id": 1,
            "planta": "TUNICHE",
            "tipo_turno": "dia",
            "fecha_operativa": "2026-05-28",
            "desde": "2026-05-28 08:00",
            "hasta": "2026-05-28 20:00",
            "responsable": "admin",
            "hora_cierre": "2026-05-28 20:05",
            "total": 0,
            "salidas": 0,
            "devoluciones": 0,
            "pendientes": 0,
            "trabajadores_pendientes": 0,
        }
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        mock_cur.fetchone.side_effect = [None, cierre_row, cierre_row, cierre_row]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        payload = {"tipo_turno": "dia", "desde": "2026-05-28T08:00", "hasta": "2026-05-28T20:00"}
        response = self.app.post('/api/cierre_turno', json=payload)
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["cerrado"])
        self.assertEqual(data["cierre"]["responsable"], "admin")

        response = self.app.post('/api/cierre_turno', json=payload)
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["cerrado"])

    @patch('routes.operation_routes.get_connection')
    def test_registrar_masivo(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Simular fetchone para las 2 prendas con categoria y tipo_control
        mock_cur.fetchone.side_effect = [
            (5, "Casco", "EPP", "RETORNABLE"),
            (10, "Guantes", "EPP", "RETORNABLE")
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.post('/api/registrar_masivo', json={
            "rut": "12.345.678-9",
            "trabajador": "Juan Perez",
            "area": "BODEGA",
            "articulo_ids": [101, 102]
        })
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertIn("Entregados (2)", data["message"])
        self.assertEqual(len(data["entregados"]), 2)

    @patch('routes.operation_routes.get_connection')
    def test_registrar_masivo_articulos_nuevos_formatos(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Simular fetchone con cantidades y categorías variadas
        mock_cur.fetchone.side_effect = [
            (100, "Bidon de agua", "CONSUMO_LIQUIDO", "CONSUMIBLE")
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        # Retiro de consumo líquido sin RUT (debería ser exitoso)
        response = self.app.post('/api/registrar_masivo', json={
            "rut": "",
            "trabajador": "",
            "area": "BODEGA",
            "articulos": [{"id": 90001, "cantidad": 5}]
        })
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["entregados"][0]["nuevo_stock"], 95)

    @patch('routes.operation_routes.get_connection')
    def test_registrar_masivo_epp_rut_obligatorio_fallo(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.side_effect = [
            (10, "Casco", "EPP", "RETORNABLE")
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        # Retiro de EPP sin RUT (debería fallar con 400)
        response = self.app.post('/api/registrar_masivo', json={
            "rut": "",
            "trabajador": "",
            "area": "BODEGA",
            "articulos": [{"id": 101, "cantidad": 1}]
        })
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data["success"])
        self.assertIn("RUT y Trabajador son obligatorios", data["message"])

    @patch('routes.worker_routes.get_connection')
    def test_pendientes(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchall.return_value = [
            {
                "transaccion_id": 1,
                "articulo_id": 101,
                "trabajador": "Juan Perez",
                "area": "BODEGA",
                "descripcion": "Casco [Única]",
                "hora_salida": "2026-05-28 09:30:00"
            }
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.get('/api/pendientes?rut=12.345.678-9')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["pendientes"]), 1)
        self.assertEqual(data["pendientes"][0]["descripcion"], "Casco [Única]")

    @patch('routes.stock_routes.get_connection')
    def test_get_registros_coalesce_sorting(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.side_effect = [
            {"total": 2},
            {"total": 2, "en_terreno": 1, "devueltos": 1}
        ]
        mock_cur.fetchall.return_value = [
            {
                "id": 1,
                "rut": "12.345.678-9",
                "trabajador": "Juan Perez",
                "area": "BODEGA",
                "articulo": "Casco [L]",
                "hora_salida": "2026-05-28 10:00:00",
                "hora_entrada": "2026-05-29 15:30:00",
                "estado": "DEVUELTO"
            },
            {
                "id": 2,
                "rut": "98.765.432-1",
                "trabajador": "Maria Lopez",
                "area": "PACKING",
                "articulo": "Guantes [M]",
                "hora_salida": "2026-05-29 11:00:00",
                "hora_entrada": None,
                "estado": "EN TERRENO"
            }
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.get('/api/registros?desde=2026-05-29&hasta=2026-05-29')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["registros"]), 2)
        self.assertEqual(data["registros"][0]["estado"], "DEVUELTO")
        self.assertEqual(data["registros"][1]["estado"], "EN TERRENO")

    @patch('routes.stock_routes.verify_admin_password')
    @patch('routes.stock_routes.get_connection')
    def test_editar_registro(self, mock_get_conn, mock_verify_admin):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_verify_admin.return_value = True

        mock_cur.fetchone.side_effect = [
            {
                "id": 1,
                "rut": "12.345.678-9",
                "trabajador": "Juan Perez",
                "area": "BODEGA",
                "cantidad": 2,
                "articulo_id": 101,
                "estado": "EN TERRENO"
            },
            {
                "stock_disponible": 10,
                "descripcion": "Casco [Única]"
            }
        ]

        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['planta'] = 'TUNICHE'

        response = self.app.patch('/api/registros/1', json={
            "rut": "98.765.432-1",
            "trabajador": "Pedro Picapiedra",
            "area": "PACKING",
            "cantidad": 5,
            "admin_password": "correct_pass"
        })

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["registro"]["rut"], "98.765.432-1")
        self.assertEqual(data["registro"]["cantidad"], 5)

if __name__ == '__main__':
    unittest.main()

