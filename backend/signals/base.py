from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from backend.db.models import Signal


class SignalDetector(ABC):
    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def detect(self) -> list[Signal]:
        """Scan markets and return a list of new Signal objects (not yet committed)."""
        ...

    def save_signals(self, signals: list[Signal]) -> int:
        for signal in signals:
            self.session.add(signal)
        self.session.commit()
        return len(signals)
