import os
import sys

REQUIRED = ["EBOOKS_API_TOKEN", "DATABASE_URL", "APP_ENV"]


def load_config() -> dict[str, str]:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        sys.exit(
            f"Не задано обов'язкові змінні середовища: {', '.join(missing)}. "
            "Скопіюйте .env.example у .env і заповніть значення."
        )
    return {name: os.environ[name] for name in REQUIRED}