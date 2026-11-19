"""Спільні фікстури та фабрика тестових об'єктів для Кібербібліотеки."""
from datetime import date, timedelta

import pytest

from cyberlibrary.loans import LOAN_DAYS, Loan


@pytest.fixture
def make_loan():
    """Фікстура-фабрика для створення об'єктів Loan з типовими значеннями."""

    def _make(
        book_id: str = "BK-101",
        book_title: str = "Дюна",
        book_format: str = "ebook",
        reader_email: str = "reader@cyberlibrary.ua",
        issued_on: date = date(2026, 11, 1),
        due_date: date | None = None,
        renewals_count: int = 0,
        has_debt: bool = False,
    ) -> Loan:
        if due_date is None:
            days = LOAN_DAYS.get(book_format, 14)
            due_date = issued_on + timedelta(days=days)
        return Loan(
            book_id=book_id,
            book_title=book_title,
            book_format=book_format,
            reader_email=reader_email,
            issued_on=issued_on,
            due_date=due_date,
            renewals_count=renewals_count,
            has_debt=has_debt,
        )

    return _make