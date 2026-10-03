import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIXEL2WEB.app import app


class MultiImageUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_generate_accepts_multiple_images(self):
        with patch("PIXEL2WEB.app.client.models.generate_content") as mock_generate:
            mock_generate.return_value = SimpleNamespace(
                text="<!DOCTYPE html><html><body>test</body></html>"
            )

            response = self.client.post(
                "/generate",
                data={
                    "language": "HTML + Tailwind CSS",
                    "mode": "photo",
                    "image": [
                        (io.BytesIO(b"fake-image-1"), "one.png"),
                        (io.BytesIO(b"fake-image-2"), "two.png"),
                    ]
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            payload = response.get_json()
            self.assertIn("code", payload)
            self.assertIn("<!DOCTYPE html>", payload["code"])
            self.assertGreaterEqual(len(mock_generate.call_args.kwargs["contents"]), 3)

    def test_generate_accepts_written_prompt_mode(self):
        with patch("PIXEL2WEB.app.client.models.generate_content") as mock_generate:
            mock_generate.return_value = SimpleNamespace(
                text="<!DOCTYPE html><html><body>hello</body></html>"
            )

            response = self.client.post(
                "/generate",
                data={
                    "language": "HTML + Tailwind CSS",
                    "mode": "text",
                    "prompt": "Create a landing page with a blue hero section",
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            payload = response.get_json()
            self.assertIn("code", payload)
            self.assertIn("<!DOCTYPE html>", payload["code"])
            self.assertIn(
                "Create a landing page with a blue hero section",
                mock_generate.call_args.kwargs["contents"][0],
            )


if __name__ == "__main__":
    unittest.main()
