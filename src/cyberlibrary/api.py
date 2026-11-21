"""HTTP API для Кібербібліотеки."""
from dataclasses import asdict
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from cyberlibrary.loans import Clock, Loan, LoanService, Notifier, QueueChecker, create_loan

app = FastAPI(title="Cyberlibrary API", version="1.0.0")


class SystemClock:
    """Реальний годинник системи."""

    def today(self) -> date:
        return date.today()


class InMemoryQueueChecker:
    """Перевірка черги на книжки в пам'яті."""

    def __init__(self, queued_books: set[str] | None = None):
        self.queued_books = queued_books or set()

    def has_queue(self, book_id: str) -> bool:
        return book_id in self.queued_books


class DummyNotifier:
    """Заглушка сервісу сповіщень для API."""

    def send(self, email: str, text: str) -> None:
        pass


def build_initial_loans() -> dict[str, Loan]:
    """Початковий набір видач у пам'яті для демонстрації та тестів."""
    today = date.today()
    return {
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
    }


def get_loans_repo() -> dict[str, Loan]:
    """Залежність сховища видач (легко перевизначається в тестах)."""
    return _LOANS_REPO


def get_loan_service() -> LoanService:
    """Залежність бізнес-сервісу продовження видач."""
    return _LOAN_SERVICE


_LOANS_REPO: dict[str, Loan] = build_initial_loans()
_LOAN_SERVICE = LoanService(
    clock=SystemClock(),
    queue_checker=InMemoryQueueChecker(),
    notifier=DummyNotifier(),
)


class LoanResponse(BaseModel):
    loan_id: str
    book_id: str
    book_title: str
    book_format: str
    reader_email: str
    issued_on: date
    due_date: date
    renewals_count: int
    has_debt: bool


@app.get("/health")
def health_check() -> dict[str, str]:
    """Перевірка працездатності сервісу."""
    return {"status": "ok"}


@app.post("/loans/{loan_id}/renew", response_model=LoanResponse)
def renew_loan_endpoint(
    loan_id: str,
    repo: dict[str, Loan] = Depends(get_loans_repo),
    service: LoanService = Depends(get_loan_service),
) -> LoanResponse:
    """Продовжує видачу книжки за її ідентифікатором."""
    loan = repo.get(loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail=f"Видачу '{loan_id}' не знайдено")

    try:
        renewed = service.renew(loan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo[loan_id] = renewed
    return LoanResponse(loan_id=loan_id, **asdict(renewed))