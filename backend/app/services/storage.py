from dataclasses import dataclass
from pathlib import Path
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


class LocalStorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        root: str | None = None,
        public_base_path: str | None = None,
    ) -> None:
        self.root = Path(root or settings.storage_root)
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


def get_storage_provider() -> StorageProvider:
    return LocalStorageProvider()
