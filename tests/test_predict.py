import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class PredictApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertIn('model_status', response.json())

    def test_predict_endpoint(self):
        response = self.client.post('/predict', json={'text': 'Urgent verify your bank account now', 'source': 'sms'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload['label'], {'safe', 'suspicious', 'scam'})
        self.assertGreaterEqual(payload['confidence'], 0.0)
        self.assertLessEqual(payload['confidence'], 1.0)


if __name__ == '__main__':
    unittest.main()
