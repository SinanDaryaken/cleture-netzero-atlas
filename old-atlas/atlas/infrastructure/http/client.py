from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from atlas.domain.models import ChangeCheckResult, FetchedAsset
from atlas.ingestion.errors import PermanentIngestionError, RetryableIngestionError


@dataclass(frozen=True)
class AdemeRelease:
    dataset_id: str
    version: str
    revision: str
    row_count: int
    asset_url: str
    filename: str
    source_updated_at: datetime | None


@dataclass(frozen=True)
class AibRelease:
    year: int
    version: str
    asset_url: str
    published_on: datetime | None


@dataclass(frozen=True)
class EmberSnapshot:
    asset: FetchedAsset
    revision: str
    row_count: int
    minimum_year: int
    maximum_year: int


class HttpAssetFetcher:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0, connect=20.0),
            headers={"User-Agent": "Cleture-Atlas/0.1 (+https://atlas.cleture.com)"},
        )

    async def resolve_defra_release(
        self,
        landing_page: str,
        *,
        reference_year: int | None = None,
        release_page: str | None = None,
    ) -> tuple[str, int]:
        if reference_year is not None and release_page is not None:
            year, publication_url = reference_year, release_page
        else:
            collection = await self._get_text(landing_page)
            soup = BeautifulSoup(collection, "html.parser")
            publications: list[tuple[int, str]] = []
            for link in soup.select("a[href]"):
                text = " ".join(link.get_text(" ", strip=True).lower().split())
                if "conversion factors 20" not in text:
                    continue
                candidate_year = self._extract_year(text)
                if candidate_year is not None and (
                    reference_year is None or candidate_year == reference_year
                ):
                    publications.append((candidate_year, urljoin(landing_page, str(link["href"]))))
            if not publications:
                target = f" for {reference_year}" if reference_year is not None else ""
                raise PermanentIngestionError(
                    f"DEFRA annual publication link was not found{target}"
                )
            year, publication_url = max(publications)
        publication = await self._get_text(publication_url)
        publication_soup = BeautifulSoup(publication, "html.parser")
        for link in publication_soup.select("a[href]"):
            text = " ".join(link.get_text(" ", strip=True).lower().split())
            if "flat file" in text and "automatic processing" in text:
                return urljoin(publication_url, str(link["href"])), year
        raise PermanentIngestionError("DEFRA automatic-processing flat file was not found")

    async def resolve_epa_release(
        self, landing_page: str, *, reference_year: int | None = None
    ) -> tuple[str, int]:
        page = await self._get_text(landing_page)
        soup = BeautifulSoup(page, "html.parser")
        releases: list[tuple[int, str]] = []
        for link in soup.select("a[href]"):
            text = " ".join(link.get_text(" ", strip=True).lower().split())
            href = str(link["href"])
            if "ghg emission factors hub" not in text or not href.lower().endswith(".xlsx"):
                continue
            url = urljoin(landing_page, href)
            year = self._extract_year(f"{text} {url}")
            if year is not None and (reference_year is None or year == reference_year):
                releases.append((year, url))
        if not releases:
            target = f" for {reference_year}" if reference_year is not None else ""
            raise PermanentIngestionError(
                f"EPA GHG Emission Factors Hub workbook was not found{target}"
            )
        year, url = max(releases)
        return url, year

    async def resolve_aib_release(
        self, landing_page: str, *, reference_year: int | None = None
    ) -> AibRelease:
        """Resolve AIB's latest annual residual-mix workbook.

        AIB keeps historical workbooks on one landing page. The release year is
        selected from the workbook link, while the methodology version is read
        from the surrounding page text. Both are retained as dataset identity.
        """
        page = await self._get_text(landing_page)
        soup = BeautifulSoup(page, "html.parser")
        releases: list[tuple[int, str]] = []
        for link in soup.select("a[href]"):
            href = str(link["href"])
            text = " ".join(link.get_text(" ", strip=True).split())
            candidate = f"{text} {href}"
            if ".xlsx" not in href.lower():
                continue
            year = self._extract_year(candidate)
            if reference_year is not None:
                if year is not None and year != reference_year:
                    continue
                releases.append((reference_year, urljoin(landing_page, href)))
            elif year is not None and any(
                token in candidate.lower()
                for token in ("residual", "excel", "calculation results", "datasheet")
            ):
                releases.append((year, urljoin(landing_page, href)))
        if not releases:
            target = f" for {reference_year}" if reference_year is not None else ""
            raise PermanentIngestionError(
                f"AIB residual-mix machine-readable workbook was not found{target}"
            )

        year, asset_url = max(releases)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        version_match = re.search(r"Version\s+(\d+(?:\.\d+)+)", page_text, flags=re.IGNORECASE)
        if version_match is None:
            raise PermanentIngestionError("AIB residual-mix version was not found")
        published_match = re.search(
            r"Version\s+\d+(?:\.\d+)+\s*,\s*(\d{4})-(\d{2})-(\d{2})",
            page_text,
            flags=re.IGNORECASE,
        )
        published_on = None
        if published_match is not None:
            published_on = datetime(
                int(published_match.group(1)),
                int(published_match.group(2)),
                int(published_match.group(3)),
                tzinfo=UTC,
            )
        return AibRelease(
            year=year,
            version=version_match.group(1),
            asset_url=asset_url,
            published_on=published_on,
        )

    async def fetch_ipcc_export(self, search_url: str) -> tuple[FetchedAsset, str, int]:
        """Export the session-scoped EFDB result table and fingerprint its data sheet.

        EFDB creates a temporary result-table name per session and emits volatile XLSX
        package metadata. The worksheet XML is the stable content boundary used for
        change detection; the original package is still retained unchanged as raw data.
        """
        try:
            search = await self._client.get(search_url)
            if search.status_code >= 500:
                raise RetryableIngestionError(f"source returned {search.status_code}")
            search.raise_for_status()
            soup = BeautifulSoup(search.text, "html.parser")
            table_name = soup.select_one("form[action*='find_ef_xls.php'] input[name='tableName']")
            if table_name is None or not table_name.get("value"):
                raise PermanentIngestionError("IPCC EFDB export table was not found")
            form = table_name.find_parent("form")
            if form is None:
                raise PermanentIngestionError("IPCC EFDB export form was not found")
            export_url = urljoin(search_url, str(form.get("action") or "find_ef_xls.php"))
            payload = {
                str(field["name"]): str(field.get("value", ""))
                for field in form.select("input[name]")
                if str(field.get("type") or "").lower() == "hidden"
            }
            exported = await self._client.post(export_url, data=payload)
            if exported.status_code >= 500:
                raise RetryableIngestionError(f"source returned {exported.status_code}")
            exported.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("IPCC EFDB export failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"IPCC EFDB export returned {error.response.status_code}"
            ) from error

        revision = self._xlsx_sheet_revision(exported.content)
        displayed = re.search(r"Displayed records:.*?/\s*([\d,]+)", search.text)
        if displayed is None:
            raise PermanentIngestionError("IPCC EFDB displayed record count was not found")
        row_count = int(displayed.group(1).replace(",", ""))
        temporary = tempfile.NamedTemporaryFile(prefix="atlas-ipcc-", suffix=".xlsx", delete=False)
        try:
            temporary.write(exported.content)
        finally:
            temporary.close()
        return (
            FetchedAsset(
                filename=f"ipcc-efdb-{revision[:12]}.xlsx",
                local_path=Path(temporary.name),
                source_url=export_url,
                mime_type=exported.headers.get("content-type")
                or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            revision,
            row_count,
        )

    async def resolve_ademe_release(self, dataset_url: str) -> AdemeRelease:
        """Resolve ADEME's public Data Fair metadata to its immutable source file.

        Data Fair's dataset metadata is the source contract. The revision deliberately
        excludes portal-level ``updatedAt`` because catalogue migrations can change it
        without changing the source data.
        """
        metadata_payload = await self._get_json(dataset_url)
        if not isinstance(metadata_payload, dict):
            raise PermanentIngestionError("ADEME Base Carbone metadata is invalid")
        metadata = metadata_payload
        if metadata.get("id") != "base-carboner":
            raise PermanentIngestionError("ADEME Base Carbone dataset id changed")
        if metadata.get("status") != "finalized":
            raise RetryableIngestionError("ADEME Base Carbone dataset is not finalized")
        file_metadata = metadata.get("file")
        if not isinstance(file_metadata, dict):
            raise PermanentIngestionError("ADEME Base Carbone file metadata is missing")
        filename = file_metadata.get("name")
        checksum = file_metadata.get("md5")
        size = file_metadata.get("size")
        if not isinstance(filename, str) or not isinstance(checksum, str):
            raise PermanentIngestionError("ADEME Base Carbone file identity is missing")
        version_match = re.search(r"_V(\d+(?:\.\d+)*)\.csv$", filename, re.IGNORECASE)
        if version_match is None:
            raise PermanentIngestionError("ADEME Base Carbone version was not found")
        row_count = metadata.get("count")
        if not isinstance(row_count, int):
            raise PermanentIngestionError("ADEME Base Carbone row count is missing")
        license_metadata = metadata.get("license")
        if not isinstance(license_metadata, dict) or "Licence Ouverte" not in str(
            license_metadata.get("title", "")
        ):
            raise PermanentIngestionError("ADEME Base Carbone open license changed")

        data_files_payload = await self._get_json(f"{dataset_url.rstrip('/')}/data-files")
        if not isinstance(data_files_payload, list):
            raise PermanentIngestionError("ADEME Base Carbone data file list is invalid")
        data_files = data_files_payload
        original = next(
            (
                item
                for item in data_files
                if isinstance(item, dict)
                and item.get("key") == "original"
                and item.get("name") == filename
            ),
            None,
        )
        if original is None or not isinstance(original.get("url"), str):
            raise PermanentIngestionError("ADEME Base Carbone original file is unavailable")

        data_updated_at = metadata.get("dataUpdatedAt")
        source_updated_at = None
        if isinstance(data_updated_at, str):
            try:
                source_updated_at = datetime.fromisoformat(data_updated_at.replace("Z", "+00:00"))
            except ValueError:
                source_updated_at = None
        signature = "|".join(
            (
                str(metadata["id"]),
                filename,
                checksum,
                str(size or ""),
                str(row_count),
                str(data_updated_at or ""),
            )
        )
        return AdemeRelease(
            dataset_id=str(metadata["id"]),
            version=version_match.group(1),
            revision=hashlib.sha256(signature.encode()).hexdigest(),
            row_count=row_count,
            asset_url=str(original["url"]),
            filename=filename,
            source_updated_at=source_updated_at,
        )

    async def fetch_ember_time_series(
        self,
        endpoint: str,
        *,
        api_key: str,
        start_date: str,
        end_date: str,
    ) -> EmberSnapshot:
        public_params = {"start_date": start_date, "end_date": end_date}
        try:
            response = await self._client.get(
                endpoint,
                params={**public_params, "api_key": api_key},
            )
            if response.status_code >= 500:
                raise RetryableIngestionError(f"Ember API returned {response.status_code}")
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("Ember API request failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"Ember API rejected the request with {error.response.status_code}"
            ) from error
        except ValueError as error:
            raise PermanentIngestionError("Ember API response is not valid JSON") from error

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise PermanentIngestionError("Ember API response contract changed")
        data = payload["data"]
        if not data:
            raise PermanentIngestionError("Ember API returned no carbon-intensity records")
        years: list[int] = []
        for item in data:
            if not isinstance(item, dict) or not str(item.get("date", "")).isdigit():
                raise PermanentIngestionError("Ember API record schema changed")
            years.append(int(str(item["date"])))
        stable_data = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        revision = hashlib.sha256(stable_data).hexdigest()
        safe_url = str(httpx.URL(endpoint).copy_merge_params(public_params))
        maximum_year = max(years)
        return EmberSnapshot(
            asset=FetchedAsset(
                filename=f"ember-yearly-carbon-intensity-{maximum_year}-{revision[:12]}.json",
                content=response.content,
                source_url=safe_url,
                mime_type=response.headers.get("content-type") or "application/json",
            ),
            revision=revision,
            row_count=len(data),
            minimum_year=min(years),
            maximum_year=maximum_year,
        )

    async def check(self, asset_url: str, previous_revision: str | None) -> ChangeCheckResult:
        try:
            response = await self._client.head(asset_url)
            if response.status_code >= 500:
                raise RetryableIngestionError(f"source returned {response.status_code}")
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("source check failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"source check returned {error.response.status_code}"
            ) from error

        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")
        signature = "|".join(
            [asset_url, etag or "", last_modified or "", response.headers.get("content-length", "")]
        )
        revision = hashlib.sha256(signature.encode()).hexdigest()
        parsed_last_modified = None
        if last_modified:
            try:
                parsed_last_modified = datetime.strptime(
                    last_modified, "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=UTC)
            except ValueError:
                parsed_last_modified = None
        changed = revision != previous_revision
        return ChangeCheckResult(
            changed=changed,
            revision=revision if changed else None,
            etag=etag,
            last_modified=parsed_last_modified,
            reason="release metadata changed" if changed else "release metadata unchanged",
        )

    async def fetch(
        self, asset_url: str, *, headers: dict[str, str] | None = None
    ) -> FetchedAsset:
        suffix = Path(httpx.URL(asset_url).path).suffix or ".bin"
        temporary = tempfile.NamedTemporaryFile(prefix="atlas-", suffix=suffix, delete=False)
        path = Path(temporary.name)
        try:
            async with self._client.stream("GET", asset_url, headers=headers) as response:
                if response.status_code >= 500:
                    raise RetryableIngestionError(f"source returned {response.status_code}")
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    temporary.write(chunk)
            temporary.close()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            temporary.close()
            await asyncio.to_thread(path.unlink, missing_ok=True)
            raise RetryableIngestionError("source download failed") from error
        except httpx.HTTPStatusError as error:
            temporary.close()
            await asyncio.to_thread(path.unlink, missing_ok=True)
            raise PermanentIngestionError(
                f"source download returned {error.response.status_code}"
            ) from error
        filename = Path(httpx.URL(asset_url).path).name or f"source{suffix}"
        return FetchedAsset(
            filename=filename,
            local_path=path,
            source_url=asset_url,
            mime_type=response.headers.get("content-type"),
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_text(self, url: str) -> str:
        try:
            response = await self._client.get(url)
            if response.status_code >= 500:
                raise RetryableIngestionError(f"source returned {response.status_code}")
            response.raise_for_status()
            return response.text
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("source page request failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"source page returned {error.response.status_code}"
            ) from error

    async def _get_json(self, url: str) -> object:
        try:
            response = await self._client.get(url)
            if response.status_code >= 500:
                raise RetryableIngestionError(f"source returned {response.status_code}")
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("source metadata request failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"source metadata returned {error.response.status_code}"
            ) from error
        except ValueError as error:
            raise PermanentIngestionError("source metadata is not valid JSON") from error

    @staticmethod
    def _xlsx_sheet_revision(content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as workbook:
                worksheet = workbook.read("xl/worksheets/sheet1.xml")
        except (zipfile.BadZipFile, KeyError) as error:
            raise PermanentIngestionError(
                "IPCC EFDB export is not a valid XLSX workbook"
            ) from error
        return hashlib.sha256(worksheet).hexdigest()

    @staticmethod
    def _extract_year(text: str) -> int | None:
        for token in text.replace(":", " ").split():
            if token.isdigit() and 2000 <= int(token) <= 2200:
                return int(token)
        return None
