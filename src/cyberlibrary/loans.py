"""Бізнес-логіка видачі та продовження книжок у Кібербібліотеці."""
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Protocol

LOAN_DAYS = {"ebook": 14, "paper": 21}   # базовий термін і крок продовження, днів
MAX_RENEWALS = 2                         # максимальна кількість продовжень
REMINDER_DAYS_BEFORE = 2                 # за скільки днів до терміну надсилати нагадування


@dataclass(frozen=True)
class Loan:
    book_id: str
    book_title: str
    book_format: str          # "ebook" або "paper"
    reader_email: str
    issued_on: date
    due_date: date
    renewals_count: int = 0
    has_debt: bool = False


def create_loan(
    book_id: str,
    book_title: str,
    book_format: str,
    reader_email: str,
    issued_on: date,
    has_debt: bool = False,
) -> Loan:
    """Створює нову видачу зі стандартним терміном (14 днів для ebook, 21 для paper)."""
    if book_format not in LOAN_DAYS:
        raise ValueError(f"Невідомий формат книжки: {book_format}")
    due_date = issued_on + timedelta(days=LOAN_DAYS[book_format])
    return Loan(
        book_id=book_id,
        book_title=book_title,
        book_format=book_format,
        reader_email=reader_email,
        issued_on=issued_on,
        due_date=due_date,
        renewals_count=0,
        has_debt=has_debt,
    )


def renew_loan(loan: Loan, today: date, has_queue: bool) -> Loan:
    """Продовжує видачу книжки за правилами Кібербібліотеки."""
    if loan.book_format not in LOAN_DAYS:
        raise ValueError(f"Невідомий формат книжки: {loan.book_format}")
    if loan.renewals_count < 0:
        raise ValueError("Кількість продовжень не може бути від'ємною")
    if loan.renewals_count >= MAX_RENEWALS:
        raise ValueError("Вичерпано ліміт продовжень (максимум 2 рази)")
    if has_queue:
        raise ValueError("Неможливо продовжити видачу: на книжку є черга")
    if loan.has_debt:
        raise ValueError("Неможливо продовжити видачу: у читача є заборгованість")
    if today > loan.due_date:
        raise ValueError("Неможливо продовжити прострочену видачу")

    extension = timedelta(days=LOAN_DAYS[loan.book_format])
    return replace(
        loan,
        due_date=loan.due_date + extension,
        renewals_count=loan.renewals_count + 1,
    )


class Clock(Protocol):
    def today(self) -> date: ...


class QueueChecker(Protocol):
    def has_queue(self, book_id: str) -> bool: ...


class Notifier(Protocol):
    def send(self, email: str, text: str) -> None: ...


class LoanService:
    """Сервіс керування видачами з впровадженням залежностей."""

    def __init__(self, clock: Clock, queue_checker: QueueChecker, notifier: Notifier):
        self.clock = clock
        self.queue_checker = queue_checker
        self.notifier = notifier

    def renew(self, loan: Loan) -> Loan:
        """Перевіряє чергу й поточну дату та продовжує видачу."""
        has_queue = self.queue_checker.has_queue(loan.book_id)
        return renew_loan(loan, today=self.clock.today(), has_queue=has_queue)

    def send_due_reminder_if_needed(self, loan: Loan) -> bool:
        """Надсилає нагадування, якщо до терміну повернення залишилося рівно 2 дні."""
        days_left = (loan.due_date - self.clock.today()).days
        if days_left == REMINDER_DAYS_BEFORE:
            self.notifier.send(
                loan.reader_email,
                f"Нагадування: термін повернення книжки «{loan.book_title}» спливає {loan.due_date}.",
            )
            return True
        return False