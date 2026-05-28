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

    @patch('routes.operation_routes.get_connection')
    def test_registrar_masivo(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Simular fetchone para validaciones de stock de los 2 artículos
        mock_cur.fetchone.side_effect = [
            (5, "Casco"),
            (10, "Guantes")
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

if __name__ == '__main__':
    unittest.main()
