from datetime import UTC, datetime

from botocore.exceptions import ClientError

from atlas.config import Settings
from atlas.domain.models import FetchedAsset
from atlas.infrastructure.storage import S3ObjectStorage
from tests.unit.test_pipeline import source


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, object]] = {}
        self.put_count = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        try:
            return self.objects[(Bucket, Key)]
        except KeyError as error:
            raise ClientError(
                {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            ) from error

    def put_object(self, **kwargs: object) -> None:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        body = kwargs["Body"]
        if hasattr(body, "read"):
            body = body.read()
        self.objects[(bucket, key)] = {"Metadata": kwargs["Metadata"], "Body": body}
        self.put_count += 1


async def test_raw_storage_is_content_addressed_and_idempotent() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(Settings(_env_file=None), client=client)
    asset = FetchedAsset(
        filename="../defra.xlsx",
        content=b"immutable",
        source_url="https://example.test/defra.xlsx",
        downloaded_at=datetime(2026, 8, 27, tzinfo=UTC),
        metadata={"asset_role": "primary"},
    )

    first = await storage.store_raw(source(), asset)
    second = await storage.store_raw(source(), asset)

    assert first == second
    assert first.object_key.startswith("sources/test/2026/08/27/")
    assert first.object_key.endswith("/defra.xlsx")
    assert first.metadata == {"asset_role": "primary"}
    assert client.put_count == 1
