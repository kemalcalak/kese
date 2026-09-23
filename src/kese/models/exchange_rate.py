"""Exchange-rate cache database model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kese.models.user import Base


class ExchangeRate(Base):
    """A TCMB exchange rate cached for the bulletin date."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "currency_code",
            "requested_date",
            name="uq_exchange_rates_code_requested_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    requested_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(
        Numeric(30, 12, asdecimal=True), nullable=False
    )
