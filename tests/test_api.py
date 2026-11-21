"""Інтеграційні тести HTTP API Кібербібліотеки."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from cyberlibrary.api import app, get_loan_service, get_loans_repo
from cyberlibrary.loans import LoanService, create_loan


class FixedClock:
    """Stub годинника для детермінованих інтеграційних тестів."""

    def __init__(self, current_date: date):
        self._current_date = current_date

    def today(self) -> date:
        return self._current_date


class FixedQueue:
    """Stub черги для інтеграційних тестів."""

    def __init__(self, queued_books: set[str] | None = None):
        self._queued_books = queued_books or set()

    def has_queue(self, book_id: str) -> bool:
        return book_id in self._queued_books


class SilentNotifier:
    """Заглушка сповіщень для інтеграційних тестів."""

    def send(self, email: str, text: str) -> None:
        pass


@pytest.fixture
def api_client():
    """Ізольований TestClient зі свіжим in-memory сховищем для кожного тесту."""
    today = date(2026, 11, 21)
    repo = {
        "LN-1": create_loan(
            book_id="BK-101",
            book_title="Дюна",
            book_format="ebook",
            reader_email="reader@cyberlibrary.ua",
            issued_on=today,
        ),
        "LN-2": create_loan(
            book_id="BK-202",
            book_title="Нейромант",
            book_format="paper",
            reader_email="debtor@cyberlibrary.ua",
            issued_on=today,
            has_debt=True,
        ),
        "LN-3": create_loan(
            book_id="BK-303",
            book_title="Фундація",
            book_format="ebook",
            reader_email="queued@cyberlibrary.ua",
            issued_on=today,
        ),
    }
    service = LoanService(
        clock=FixedClock(today),
        queue_checker=FixedQueue(queued_books={"BK-303"}),
        notifier=SilentNotifier(),
    )

    app.dependency_overrides[get_loans_repo] = lambda: repo
    app.dependency_overrides[get_loan_service] = lambda: service

    with TestClient(app) as client:
        yield client, repo

    app.dependency_overrides.clear()


def test_health_endpoint_returns_ok(api_client):
    """Перевірка системного ендпоінта GET /health."""
    client, _ = api_client
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_renew_loan_success_updates_due_date_and_count(api_client):
    """Успішне продовження електронної книжки (+14 днів, renewals_count: 0 -> 1)."""
    client, repo = api_client
    old_due_date = repo["LN-1"].due_date

    response = client.post("/loans/LN-1/renew")

    assert response.status_code == 200
    payload = response.json()
    assert payload["loan_id"] == "LN-1"
    assert payload["renewals_count"] == 1
    assert payload["due_date"] == (old_due_date + timedelta(days=14)).isoformat()


def test_renew_loan_not_found_returns_404(api_client):
    """Запит на продовження неіснуючої видачі повертає 404 Not Found."""
    client, _ = api_client
    response = client.post("/loans/LN-999/renew")

    assert response.status_code == 404
    assert response.json()["detail"] == "Видачу 'LN-999' не знайдено"


def test_renew_loan_rejected_when_reader_has_debt_returns_400(api_client):
    """Бізнес-заборона продовження при наявності боргу повертає 400 Bad Request."""
    client, _ = api_client
    response = client.post("/loans/LN-2/renew")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Неможливо продовжити видачу: у читача є заборгованість"
    )


def test_renew_loan_rejected_when_book_in_queue_returns_400(api_client):
    """Бізнес-заборона продовження при наявності черги повертає 400 Bad Request."""
    client, _ = api_client
    response = client.post("/loans/LN-3/renew")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Неможливо продовжити видачу: на книжку є черга"
    )


def test_renew_loan_rejected_after_max_renewals_returns_400(api_client):
    """Третє поспіль продовження через API відхиляється з кодом 400."""
    client, _ = api_client

    assert client.post("/loans/LN-1/renew").status_code == 200
    assert client.post("/loans/LN-1/renew").status_code == 200

    third_response = client.post("/loans/LN-1/renew")
    assert third_response.status_code == 400
    assert (
        third_response.json()["detail"]
        == "Вичерпано ліміт продовжень (максимум 2 рази)"
    )