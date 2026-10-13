import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


DAILY_RECIPIENT_LIMIT = 999
RECIPIENT_COUNTS_FILE = (
    Path(__file__).resolve().parent.parent
    / "sender_logs"
    / "accounts_recipient_counts.json"
)


class AccountsRecipientManager:
    def __init__(
        self,
        counts_file: Path = RECIPIENT_COUNTS_FILE,
        daily_limit: int = DAILY_RECIPIENT_LIMIT,
    ):
        if daily_limit <= 0:
            raise ValueError("daily_limit must be positive")
        self.counts_file = Path(counts_file)
        self.daily_limit = daily_limit
        self._lock = threading.RLock()

    @staticmethod
    def _period_date(now: Optional[datetime] = None) -> str:
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return (
            current_time.astimezone(timezone.utc) - timedelta(minutes=1)
        ).date().isoformat()

    @staticmethod
    def _account_key(account_email: str) -> str:
        account_key = account_email.strip().casefold()
        if not account_key:
            raise ValueError("account_email must not be empty")
        return account_key

    def _read_state(self, period_date: str) -> dict:
        if not self.counts_file.exists():
            return {"date": period_date, "accounts": {}}

        with self.counts_file.open("r", encoding="utf-8") as handle:
            state = json.load(handle)

        if not isinstance(state, dict):
            raise ValueError(f"Invalid recipient-count data in {self.counts_file}")

        stored_date = state.get("date")
        accounts = state.get("accounts")
        if not isinstance(stored_date, str) or not isinstance(accounts, dict):
            raise ValueError(f"Invalid recipient-count data in {self.counts_file}")
        for account_email, count in accounts.items():
            if (
                not isinstance(account_email, str)
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                raise ValueError(f"Invalid recipient-count data in {self.counts_file}")
        return state

    def _write_state(self, state: dict) -> None:
        self.counts_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.counts_file.parent,
                prefix=f"{self.counts_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = handle.name
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary_path, self.counts_file)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _get_state(self, now: Optional[datetime] = None) -> dict:
        period_date = self._period_date(now)
        state = self._read_state(period_date)
        if state["date"] != period_date:
            state = {"date": period_date, "accounts": {}}
            self._write_state(state)
        elif not self.counts_file.exists():
            self._write_state(state)
        return state

    def sent_count(self, account_email: str, now: Optional[datetime] = None) -> int:
        account_key = self._account_key(account_email)
        with self._lock:
            state = self._get_state(now)
            return state["accounts"].get(account_key, 0)

    def remaining(self, account_email: str, now: Optional[datetime] = None) -> int:
        return max(0, self.daily_limit - self.sent_count(account_email, now))

    def record_sent(
        self, account_email: str, count: int, now: Optional[datetime] = None
    ) -> int:
        account_key = self._account_key(account_email)
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("count must be a positive integer")

        with self._lock:
            state = self._get_state(now)
            updated_count = state["accounts"].get(account_key, 0) + count
            if updated_count > self.daily_limit:
                raise ValueError(
                    f"Recording {count} recipients would exceed the daily limit "
                    f"of {self.daily_limit} for {account_email}"
                )
            state["accounts"][account_key] = updated_count
            self._write_state(state)
            return updated_count
