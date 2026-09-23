"""Exchange-rate fetching, caching, and conversion rules."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from kese.core.settings import Settings
from kese.models import ExchangeRate
from kese.repositories.exchange_rates import find_cached_rate, save_rates

MAX_RETRIES = 3
MAX_FALLBACK_DAYS = 7


class CurrencyNotFoundError(Exception):
    """Raised when a bulletin does not contain the requested currency."""


class BulletinUnavailableError(Exception):
    """Raised when TCMB cannot provide a bulletin."""


def _parse_bulletin(xml: str) -> tuple[date, dict[str, Decimal]]:
    """Parse TCMB's XML bulletin and scale quotes by their unit count."""
    root = ElementTree.fromstring(xml)
    day, month, year = root.attrib["Tarih"].split(".")
    bulletin_date = date(int(year), int(month), int(day))
    rates: dict[str, Decimal] = {}
    for currency in root.findall("Currency"):
        code = currency.attrib.get("CurrencyCode")
        unit_text = currency.findtext("Unit")
        selling_text = currency.findtext("ForexSelling")
        if code is None or unit_text is None or selling_text is None:
            continue
        try:
            rates[code.upper()] = Decimal(selling_text) / Decimal(unit_text)
        except InvalidOperation:
            continue
    return bulletin_date, rates


def _bulletin_url(day: date) -> str:
    """Build the TCMB bulletin URL for a calendar day."""
    return f"https://www.tcmb.gov.tr/kurlar/{day:%Y%m}/{day:%d%m%Y}.xml"


async def _fetch_bulletin(day: date) -> tuple[date, dict[str, Decimal]] | None:
    """Fetch one bulletin, retrying transient network failures."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(_bulletin_url(day))
            except httpx.RequestError as error:
                if attempt == MAX_RETRIES - 1:
                    raise BulletinUnavailableError from error
                continue
            if response.status_code == 404:
                return None
            if response.is_success:
                try:
                    return _parse_bulletin(response.text)
                except (ElementTree.ParseError, KeyError, ValueError) as error:
                    raise BulletinUnavailableError from error
            raise BulletinUnavailableError
    raise BulletinUnavailableError


async def get_rate(
    session: AsyncSession, code: str, requested_date: date, settings: Settings
) -> ExchangeRate:
    """Return a cached rate or fetch the requested bulletin with date fallback."""
    normalized_code = code.upper()
    cached = await find_cached_rate(session, normalized_code, requested_date)
    if cached is not None:
        return cached

    for days_back in range(MAX_FALLBACK_DAYS):
        bulletin = await _fetch_bulletin(requested_date - timedelta(days=days_back))
        if bulletin is None:
            continue
        bulletin_date, rates = bulletin
        await save_rates(session, requested_date, bulletin_date, rates)
        selected_rate = rates.get(normalized_code)
        if selected_rate is None:
            raise CurrencyNotFoundError
        cached = await find_cached_rate(session, normalized_code, requested_date)
        if cached is None:
            raise BulletinUnavailableError
        return cached
    raise BulletinUnavailableError


async def convert(
    session: AsyncSession,
    amount: Decimal,
    source: str,
    target: str,
    requested_date: date,
    settings: Settings,
) -> tuple[Decimal, Decimal, Decimal]:
    """Convert an amount through TRY using only Decimal arithmetic."""
    source_code = source.upper()
    target_code = target.upper()
    source_rate = Decimal(1)
    target_rate = Decimal(1)
    if source_code != "TRY":
        source_rate = (
            await get_rate(session, source_code, requested_date, settings)
        ).rate
    if target_code != "TRY":
        target_rate = (
            await get_rate(session, target_code, requested_date, settings)
        ).rate
    rate = source_rate / target_rate
    return amount, rate, amount * rate
