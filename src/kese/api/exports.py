"""Transaction export HTTP endpoints."""

import csv
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.services.exports import build_xlsx, get_export_rows

router = APIRouter(prefix="/exports", tags=["exports"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]


def csv_chunks(
    rows: Sequence[tuple[datetime, str, str, str | None, Decimal]],
) -> Iterator[str]:
    """Yield CSV header and rows without assembling the response body."""
    header = StringIO()
    csv.writer(header).writerow(
        ["date", "account", "description", "category", "amount"]
    )
    yield header.getvalue()
    for occurred_at, account, description, category, amount in rows:
        line = StringIO()
        csv.writer(line).writerow(
            [
                occurred_at.astimezone(UTC).date().isoformat(),
                account,
                description,
                category or "",
                str(amount),
            ]
        )
        yield line.getvalue()


async def export_data(
    session: AsyncSession, user: User, since: str, until: str
) -> list[tuple[datetime, str, str, str | None, Decimal]]:
    """Fetch export rows and convert invalid date ranges to HTTP 422."""
    try:
        return await get_export_rows(session, user.id, since, until)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.get("/transactions.csv")
async def transactions_csv(
    session: Session,
    user: CurrentUser,
    since: str = Query(...),
    until: str = Query(...),
) -> StreamingResponse:
    """Stream the caller's transactions as CSV."""
    rows = await export_data(session, user, since, until)
    return StreamingResponse(
        csv_chunks(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/transactions.xlsx")
async def transactions_xlsx(
    session: Session,
    user: CurrentUser,
    since: str = Query(...),
    until: str = Query(...),
) -> Response:
    """Return the caller's transactions as an XLSX workbook."""
    rows = await export_data(session, user, since, until)
    return Response(
        content=build_xlsx(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=transactions.xlsx"},
    )
