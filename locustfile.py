"""Сценарій навантажувального тестування API Кібербібліотеки (Варіант 12)."""
from locust import HttpUser, between, task


class CyberlibraryUser(HttpUser):
    """Імітує читачів та сервісні перевірки під навантаженням."""

    wait_time = between(0.1, 0.5)

    @task(3)
    def check_health(self):
        """Частий запит перевірки стану сервісу GET /health."""
        self.client.get("/health", name="GET /health")

    @task(2)
    def renew_valid_loan(self):
        """Запит на продовження видачі LN-1 (перші 2 рази — 200, далі очікувано 400)."""
        with self.client.post(
            "/loans/LN-1/renew",
            name="POST /loans/{id}/renew (valid/limit)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 400):
                response.success()
            else:
                response.failure(f"Неочікуваний статус: {response.status_code}")

    @task(1)
    def renew_debtor_loan(self):
        """Запит на продовження видачі читача з боргом LN-2 (очікувано 400)."""
        with self.client.post(
            "/loans/LN-2/renew",
            name="POST /loans/{id}/renew (debt_reject)",
            catch_response=True,
        ) as response:
            if response.status_code == 400:
                response.success()
            else:
                response.failure(f"Очікувався статус 400, отримано: {response.status_code}")