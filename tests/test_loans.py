"""Модульні тести правила продовження видачі книжок."""
from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from cyberlibrary.loans import LoanService, create_loan, renew_loan


class FakeClock:
    """Stub годинника: повертає фіксовану поточну дату, задану тестом."""

    def __init__(self, current_date: date):
        self._current_date = current_date

    def today(self) -> date:
        return self._current_date


class StubQueue:
    """Stub черги на книжку: повертає заздалегідь заданий статус наявності черги."""

    def __init__(self, queued_books: set[str] | None = None):
        self._queued_books = queued_books or set()

    def has_queue(self, book_id: str) -> bool:
        return book_id in self._queued_books


# 1. Тести створення видачі (create_loan)
@pytest.mark.parametrize(
    "book_format, expected_days",
    [
        ("ebook", 14),  # клас: електронна книжка видається на 14 днів
        ("paper", 21),  # клас: паперова книжка видається на 21 день
    ],
)
def test_create_loan_sets_standard_due_date(book_format, expected_days):
    issued = date(2026, 11, 1)
    loan = create_loan(
        book_id="BK-1",
        book_title="Нейромант",
        book_format=book_format,
        reader_email="user@example.com",
        issued_on=issued,
    )
    assert (loan.due_date - loan.issued_on).days == expected_days
    assert loan.renewals_count == 0


def test_create_loan_unknown_format_raises():
    with pytest.raises(ValueError, match="Невідомий формат книжки"):
        create_loan("BK-1", "Книга", "audiobook", "user@example.com", date(2026, 11, 1))


# 2. Параметризовані тести меж та класів для renew_loan
@pytest.mark.parametrize(
    "book_format, renewals_count, days_from_due, expected_added_days",
    [
        ("ebook", 0, -5, 14),  # ebook, перше продовження (0 -> 1), завчасно (-5 днів)
        ("ebook", 1, 0, 14),   # межа: останнє продовження (1 -> 2), у день терміну (0 днів)
        ("paper", 0, -3, 21),  # paper, перше продовження (0 -> 1), завчасно
        ("paper", 1, 0, 21),   # межа: paper, останнє продовження (1 -> 2), у день терміну
    ],
)
def test_renew_loan_success_cases(
    make_loan, book_format, renewals_count, days_from_due, expected_added_days
):
    loan = make_loan(book_format=book_format, renewals_count=renewals_count)
    today = loan.due_date + timedelta(days=days_from_due)

    renewed = renew_loan(loan, today=today, has_queue=False)

    assert renewed.due_date == loan.due_date + timedelta(days=expected_added_days)
    assert renewed.renewals_count == renewals_count + 1


# 3. Негативні тести (таблиця рішень R2–R6 та недопустимі дані)
@pytest.mark.parametrize(
    "renewals_count",
    [
        2,  # межа: ліміт рівно 2 продовження вже вичерпано (R2)
        3,  # типове значення понад ліміт
    ],
)
def test_renew_loan_rejected_when_limit_reached(make_loan, renewals_count):
    loan = make_loan(renewals_count=renewals_count)
    with pytest.raises(ValueError, match="ліміт продовжень"):
        renew_loan(loan, today=loan.issued_on, has_queue=False)


def test_renew_loan_rejected_when_queue_exists(make_loan):
    """Правило R3: на книжку є черга."""
    loan = make_loan()
    with pytest.raises(ValueError, match="є черга"):
        renew_loan(loan, today=loan.issued_on, has_queue=True)


def test_renew_loan_rejected_when_reader_has_debt(make_loan):
    """Правило R4: читач має активну заборгованість."""
    loan = make_loan(has_debt=True)
    with pytest.raises(ValueError, match="заборгованість"):
        renew_loan(loan, today=loan.issued_on, has_queue=False)


def test_renew_loan_rejected_when_overdue_by_one_day(make_loan):
    """Правило R5, межа: прострочення на +1 день після due_date."""
    loan = make_loan()
    overdue_day = loan.due_date + timedelta(days=1)
    with pytest.raises(ValueError, match="прострочену видачу"):
        renew_loan(loan, today=overdue_day, has_queue=False)


@pytest.mark.parametrize(
    "book_format, renewals_count, expected_match",
    [
        ("clay_tablet", 0, "Невідомий формат"),   # недопустимий формат книжки
        ("ebook", -1, "не може бути від'ємною"),  # нижня недопустима межа лічильника
    ],
)
def test_renew_loan_invalid_state_raises(make_loan, book_format, renewals_count, expected_match):
    loan = make_loan(book_format=book_format, renewals_count=renewals_count)
    with pytest.raises(ValueError, match=expected_match):
        renew_loan(loan, today=loan.issued_on, has_queue=False)


# ── 4. Тести сервісу зі Stub годинника, Stub черги та Mock сповіщень ─
def test_service_renews_loan_when_no_queue(make_loan):
    loan = make_loan(book_id="BK-42", book_format="paper")
    clock = FakeClock(loan.due_date)
    queue = StubQueue(queued_books={"BK-99"})  # черга на іншу книжку
    service = LoanService(clock=clock, queue_checker=queue, notifier=Mock())

    renewed = service.renew(loan)

    assert renewed.renewals_count == 1
    assert renewed.due_date == loan.due_date + timedelta(days=21)


def test_service_blocks_renewal_when_book_is_in_stub_queue(make_loan):
    loan = make_loan(book_id="BK-42")
    clock = FakeClock(loan.issued_on)
    queue = StubQueue(queued_books={"BK-42"})
    service = LoanService(clock=clock, queue_checker=queue, notifier=Mock())

    with pytest.raises(ValueError, match="є черга"):
        service.renew(loan)


@pytest.mark.parametrize(
    "days_before_due, expected_sent",
    [
        (3, False),  # межа: за 3 дні — ще рано
        (2, True),   # межа: рівно за 2 дні — надсилаємо нагадування
        (1, False),  # межа: за 1 день — нагадування вже не дублюється
        (0, False),  # межа: день терміну повернення
    ],
)
def test_service_reminder_boundary_days(make_loan, days_before_due, expected_sent):
    loan = make_loan(book_title="Фундація", reader_email="ivan@cyberlibrary.ua")
    clock = FakeClock(loan.due_date - timedelta(days=days_before_due))
    notifier = Mock()
    service = LoanService(clock=clock, queue_checker=StubQueue(), notifier=notifier)

    was_sent = service.send_due_reminder_if_needed(loan)

    assert was_sent is expected_sent
    if expected_sent:
        notifier.send.assert_called_once_with(
            "ivan@cyberlibrary.ua",
            f"Нагадування: термін повернення книжки «Фундація» спливає {loan.due_date}.",
        )
    else:
        notifier.send.assert_not_called()

# 5. Додаткове завдання: перевірка тексту через mock ──
def test_reminder_message_contains_title_and_due_date_via_mock_args(make_loan):
    """Перевірка змісту нагадування через інспекцію аргументів виклику mock."""
    loan = make_loan(book_title="1984", reader_email="olena@cyberlibrary.ua")
    clock = FakeClock(loan.due_date - timedelta(days=2))
    notifier = Mock()
    service = LoanService(clock=clock, queue_checker=StubQueue(), notifier=notifier)

    service.send_due_reminder_if_needed(loan)

    notifier.send.assert_called_once()
    sent_email, sent_text = notifier.send.call_args.args
    assert sent_email == "olena@cyberlibrary.ua"
    assert "1984" in sent_text
    assert str(loan.due_date) in sent_text