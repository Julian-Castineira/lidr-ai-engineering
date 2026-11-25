"""Estimación real de extremo a extremo (con coste). Solo se ejecuta con `pytest -m live`."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

pytestmark = pytest.mark.live

# Transcripción ficticia y corta: una llamada de unos 3.000 tokens de entrada.
TRANSCRIPTION = (
    "Comercial: Gracias por la reunión. Resumo lo que necesitáis.\n"
    "Cliente: Somos una escuela de música. Queremos una landing para la campaña de "
    "matrícula con un formulario que cree el contacto en HubSpot, y un blog sencillo "
    "para publicar dos noticias al mes. Tenemos logotipo pero no diseño web.\n"
    "Comercial: ¿Plazo?\n"
    "Cliente: Que esté lista en un mes."
)


def test_real_estimation_end_to_end() -> None:
    settings = Settings()
    if settings.anthropic_api_key is None:
        pytest.skip("ANTHROPIC_API_KEY no configurada")
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/estimate", json={"transcription": TRANSCRIPTION})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert "| Tarea | Rol | Horas | Coste (EUR) |" in body["estimation"]
    assert "Total de horas" in body["estimation"]
    assert "Coste total" in body["estimation"]
    assert body["provider"] == "anthropic"
    assert body["usage"]["input_tokens"] > 0
    assert body["usage"]["output_tokens"] > 0
    assert body["cost_usd"] is not None
    assert body["cost_usd"] > 0
    assert body["finish_reason"] == "stop"
