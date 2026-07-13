from io import BytesIO

import pytest

from app.core.config import Settings
from app.services.storage import S3StorageProvider


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.objects: dict[str, bytes] = {}

    def put_object(self, **kwargs) -> object:
        self.put_calls.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(self, **kwargs) -> object:
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs) -> object:
        self.delete_calls.append(kwargs)
        return {}


class FakeS3MissingObjectError(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class MissingS3Client(FakeS3Client):
    def get_object(self, **kwargs) -> object:
        raise FakeS3MissingObjectError("missing object")



def test_s3_storage_provider_saves_metadata_and_deletes_by_key() -> None:
    client = FakeS3Client()
    provider = S3StorageProvider(
        bucket="cleanops-photos",
        private_bucket="cleanops-private-photos",
        region="ap-northeast-2",
        access_key_id="access",
        secret_access_key="secret",
        public_base_url="https://cdn.cleanops.example/photos",
        client=client,
    )

    stored = provider.save(
        data=b"\x89PNG\r\n\x1a\ntest",
        file_name="../after.PNG",
        content_type="image/png",
    )
    provider.delete(stored.storage_key)

    assert stored.storage_key.startswith("photos/")
    assert stored.storage_key.endswith(".png")
    assert stored.file_url == f"https://cdn.cleanops.example/photos/{stored.storage_key}"
    assert stored.file_name == "after.PNG"
    assert stored.file_size == 12
    assert client.put_calls[0]["Bucket"] == "cleanops-photos"
    assert client.put_calls[0]["Key"] == stored.storage_key
    assert client.put_calls[0]["ContentType"] == "image/png"
    assert client.delete_calls == [{"Bucket": "cleanops-photos", "Key": stored.storage_key}]


def test_s3_storage_provider_saves_private_file_without_public_url_and_reads_by_key() -> None:
    client = FakeS3Client()
    provider = S3StorageProvider(
        bucket="cleanops-photos",
        private_bucket="cleanops-private-photos",
        region="ap-northeast-2",
        access_key_id="access",
        secret_access_key="secret",
        public_base_url="https://cdn.cleanops.example/photos",
        client=client,
    )

    stored = provider.save_private(
        data=b"\x89PNG\r\n\x1a\nprivate",
        file_name="../customer-as.PNG",
        content_type="image/png",
    )

    assert stored.storage_key.startswith("private/photos/")
    assert stored.storage_key.endswith(".png")
    assert stored.file_url == ""
    assert stored.file_name == "customer-as.PNG"
    assert provider.read(stored.storage_key) == b"\x89PNG\r\n\x1a\nprivate"
    assert client.put_calls[0]["Bucket"] == "cleanops-private-photos"
    assert client.put_calls[0]["Key"] == stored.storage_key
    assert client.put_calls[0]["ContentType"] == "image/png"


def test_s3_storage_provider_translates_missing_object_to_file_not_found() -> None:
    provider = S3StorageProvider(
        bucket="cleanops-photos",
        private_bucket="cleanops-private-photos",
        region="ap-northeast-2",
        access_key_id="access",
        secret_access_key="secret",
        public_base_url="https://cdn.cleanops.example/photos",
        client=MissingS3Client(),
    )

    with pytest.raises(FileNotFoundError):
        provider.read("private/photos/missing.png")


def test_s3_storage_provider_requires_public_url_and_credentials() -> None:
    with pytest.raises(RuntimeError, match="s3_storage_missing_settings"):
        S3StorageProvider(
            bucket="bucket",
            access_key_id="",
            secret_access_key="",
            public_base_url="",
        )


def test_production_requires_object_storage_settings() -> None:
    with pytest.raises(ValueError, match="production requires object storage"):
        Settings(environment="production", secret_key="x" * 32)

    with pytest.raises(ValueError, match="production s3 storage missing settings"):
        Settings(environment="production", secret_key="x" * 32, storage_provider="s3")


def test_production_rejects_public_private_bucket_reuse() -> None:
    with pytest.raises(ValueError, match="separate private S3 bucket"):
        Settings(
            environment="production",
            secret_key="x" * 32,
            storage_provider="s3",
            s3_bucket="bucket",
            s3_private_bucket="bucket",
            s3_access_key_id="access",
            s3_secret_access_key="secret",
            s3_public_base_url="https://cdn.example.com",
        )
