"""Transaction export business rules."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from kese.repositories.exports import export_transactions
from kese.services.reports import export_range


async def get_export_rows(
    session: AsyncSession, user_id: UUID, since: str, until: str
) -> list[tuple[datetime, str, str, str | None, Decimal]]:
    """Fetch the caller's transaction rows for an inclusive UTC day range."""
    start, end = export_range(since, until)
    return await export_transactions(session, user_id, start, end)


def build_xlsx(
    rows: Sequence[tuple[datetime, str, str, str | None, Decimal]],
) -> bytes:
    """Build an XLSX workbook with Decimal amounts as numeric cells."""
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("workbook has no active worksheet")
    sheet.append(["date", "account", "description", "category", "amount"])
    for occurred_at, account, description, category, amount in rows:
        sheet.append(
            [
                occurred_at.astimezone(UTC).date().isoformat(),
                account,
                description,
                category or "",
                amount,
            ]
        )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
