from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.core.config import settings


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    file_url: str
    file_name: str
    file_size: int
    content_type: str


class StorageProvider:
    def save(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        raise NotImplementedError

    def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        raise NotImplementedError

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError


class S3Client(Protocol):
    def put_object(self, **kwargs) -> object:
        ...

    def get_object(self, **kwargs) -> object:
        ...

    def delete_object(self, **kwargs) -> object:
        ...


class LocalStorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        root: str | None = None,
        private_root: str | None = None,
        public_base_path: str | None = None,
    ) -> None:
        self.root = Path(root or settings.storage_root)
        self.private_root = Path(private_root or settings.storage_private_root)
        self.public_base_path = (public_base_path or settings.storage_public_base_path).rstrip("/")

    def save(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        safe_name = Path(file_name).name or "upload"
        suffix = Path(safe_name).suffix.lower()
        storage_key = f"photos/{uuid4().hex}{suffix}"
        target = self.root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        return StoredFile(
            storage_key=storage_key,
            file_url=f"{self.public_base_path}/{storage_key}",
            file_name=safe_name,
            file_size=len(data),
            content_type=content_type,
        )

    def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        safe_name = Path(file_name).name or "upload"
        suffix = Path(safe_name).suffix.lower()
        storage_key = f"private/photos/{uuid4().hex}{suffix}"
        target = self._target_for_key(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        return StoredFile(
            storage_key=storage_key,
            file_url="",
            file_name=safe_name,
            file_size=len(data),
            content_type=content_type,
        )

    def read(self, storage_key: str) -> bytes:
        return self._target_for_key(storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        target = self._target_for_key(storage_key)
        try:
            target.unlink()
        except FileNotFoundError:
            return

    def _target_for_key(self, storage_key: str) -> Path:
        if storage_key.startswith("private/"):
            return self.private_root / storage_key.removeprefix("private/")
        return self.root / storage_key


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        bucket: str | None = None,
        private_bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        public_base_url: str | None = None,
        client: S3Client | None = None,
    ) -> None:
        self.bucket = bucket if bucket is not None else settings.s3_bucket
        self.private_bucket = (
            private_bucket
            if private_bucket is not None
            else settings.s3_private_bucket
        )
        self.region = region if region is not None else settings.s3_region
        self.endpoint_url = endpoint_url if endpoint_url is not None else settings.s3_endpoint_url
        self.access_key_id = (
            access_key_id if access_key_id is not None else settings.s3_access_key_id
        )
        self.secret_access_key = (
            secret_access_key if secret_access_key is not None else settings.s3_secret_access_key
        )
        self.public_base_url = (
            public_base_url if public_base_url is not None else settings.s3_public_base_url
        ).rstrip("/")
        self._client = client
        self._validate_settings()

    def save(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        safe_name = Path(file_name).name or "upload"
        suffix = Path(safe_name).suffix.lower()
        storage_key = f"photos/{uuid4().hex}{suffix}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=data,
            ContentType=content_type,
        )
        return StoredFile(
            storage_key=storage_key,
            file_url=f"{self.public_base_url}/{storage_key}",
            file_name=safe_name,
            file_size=len(data),
            content_type=content_type,
        )

    def save_private(self, *, data: bytes, file_name: str, content_type: str) -> StoredFile:
        safe_name = Path(file_name).name or "upload"
        suffix = Path(safe_name).suffix.lower()
        storage_key = f"private/photos/{uuid4().hex}{suffix}"
        self.client.put_object(
            Bucket=self.private_bucket,
            Key=storage_key,
            Body=data,
            ContentType=content_type,
        )
        return StoredFile(
            storage_key=storage_key,
            file_url="",
            file_name=safe_name,
            file_size=len(data),
            content_type=content_type,
        )

    def read(self, storage_key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.private_bucket, Key=storage_key)
        except Exception as exc:
            if is_s3_missing_object_error(exc):
                raise FileNotFoundError(storage_key) from exc
            raise
        return response["Body"].read()

    def delete(self, storage_key: str) -> None:
        bucket = self.private_bucket if storage_key.startswith("private/") else self.bucket
        self.client.delete_object(Bucket=bucket, Key=storage_key)

    @property
    def client(self) -> S3Client:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("boto3_required_for_s3_storage") from exc
            self._client = boto3.client(
                "s3",
                region_name=self.region or None,
                endpoint_url=self.endpoint_url or None,
                aws_access_key_id=self.access_key_id or None,
                aws_secret_access_key=self.secret_access_key or None,
            )
        return self._client

    def _validate_settings(self) -> None:
        missing = [
            name
            for name, value in {
                "s3_bucket": self.bucket,
                "s3_private_bucket": self.private_bucket,
                "s3_access_key_id": self.access_key_id,
                "s3_secret_access_key": self.secret_access_key,
                "s3_public_base_url": self.public_base_url,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError("s3_storage_missing_settings: " + ", ".join(missing))


def get_storage_provider() -> StorageProvider:
    if settings.storage_provider.strip().lower() == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()


def is_s3_missing_object_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error")
    if not isinstance(error, dict):
        return False
    return error.get("Code") in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}
