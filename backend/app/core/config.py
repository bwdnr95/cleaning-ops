from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Cleaning Ops Control Center API"
    app_version: str = "0.1.0"
    environment: str = "development"
    business_timezone: str = "Asia/Seoul"
    database_url: str = "sqlite:///./cleaning_ops.db"
    frontend_url: str = "http://localhost:5173"
    kakao_channel_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 1440
    admin_refresh_token_ttl_days: int = 7
    partner_refresh_token_ttl_days: int = 7
    login_max_attempts: int = 10
    login_lockout_minutes: int = 15
    customer_verify_max_attempts: int = 10
    customer_verify_lockout_minutes: int = 15
    storage_provider: str = "local"
    storage_root: str = "local_storage"
    storage_private_root: str = "local_private_storage"
    storage_public_base_path: str = "/uploads"
    s3_bucket: str = ""
    s3_private_bucket: str = ""
    s3_region: str = "ap-northeast-2"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""
    photo_max_upload_bytes: int = 10 * 1024 * 1024
    customer_as_max_files: int = 10
    customer_as_max_upload_bytes: int = 30 * 1024 * 1024
    customer_as_request_body_overhead_bytes: int = 1024 * 1024
    automation_send_partner_assignment: bool = True
    automation_send_schedule_confirmed: bool = True
    automation_send_customer_photo_ready: bool = False
    automation_send_customer_balance_due: bool = True
    automation_recurring_order_scheduler_enabled: bool = True
    automation_recurring_order_hour: int = 0
    automation_recurring_order_minute: int = 5
    automation_day_before_notice_scheduler_enabled: bool = True
    automation_day_before_notice_hour: int = 10
    automation_day_before_notice_minute: int = 0
    automation_notification_recovery_enabled: bool = True
    automation_notification_recovery_interval_seconds: int = 60
    message_pending_retry_after_minutes: int = 15
    message_provider: str = "mock"
    solapi_api_key: str = ""
    solapi_api_secret: str = ""
    solapi_sender_number: str = ""
    solapi_send_url: str = "https://api.solapi.com/messages/v4/send-many/detail"
    solapi_timeout_seconds: float = 10.0
    solapi_webhook_secret: str = ""
    solapi_kakao_channel_id: str = ""
    solapi_kakao_pf_id: str = ""
    solapi_kakao_sender_key: str = ""
    solapi_kakao_template_customer_schedule_confirmed: str = ""
    solapi_kakao_template_customer_day_before: str = ""
    solapi_kakao_template_partner_job_assignment: str = ""
    solapi_kakao_template_customer_photo_ready: str = ""
    solapi_kakao_template_customer_balance_due: str = ""
    solapi_kakao_template_customer_quote: str = ""
    solapi_kakao_template_partner_customer_info: str = ""
    solapi_kakao_template_partner_as_request: str = ""
    solapi_kakao_template_customer_as_notice: str = ""
    solapi_alimtalk_fallback_sms: bool = True
    sentry_dsn: str = ""
    sentry_environment: str = ""
    sentry_release: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_send_default_pii: bool = False

    def model_post_init(self, __context: object) -> None:
        provider = self.message_provider.strip().lower()
        if provider not in {"", "mock", "solapi"}:
            raise ValueError(f"unsupported message_provider: {self.message_provider}")
        storage_provider = self.storage_provider.strip().lower()
        if storage_provider not in {"local", "s3"}:
            raise ValueError(f"unsupported storage_provider: {self.storage_provider}")
        try:
            ZoneInfo(self.business_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unsupported business_timezone: {self.business_timezone}") from exc
        if not 0 <= self.automation_day_before_notice_hour <= 23:
            raise ValueError("automation_day_before_notice_hour must be between 0 and 23")
        if not 0 <= self.automation_day_before_notice_minute <= 59:
            raise ValueError("automation_day_before_notice_minute must be between 0 and 59")
        if self.message_pending_retry_after_minutes < 1:
            raise ValueError("message_pending_retry_after_minutes must be at least 1")
        if self.automation_notification_recovery_interval_seconds < 10:
            raise ValueError(
                "automation_notification_recovery_interval_seconds must be at least 10"
            )
        if not 0 <= self.automation_recurring_order_hour <= 23:
            raise ValueError("automation_recurring_order_hour must be between 0 and 23")
        if not 0 <= self.automation_recurring_order_minute <= 59:
            raise ValueError("automation_recurring_order_minute must be between 0 and 59")
        if self.customer_as_request_body_overhead_bytes < 0:
            raise ValueError("customer_as_request_body_overhead_bytes must be non-negative")

        if self.environment == "production":
            insecure_secret_keys = {
                "change-me-in-production",
                "replace-with-at-least-32-random-characters",
            }
            if self.secret_key.strip().lower() in insecure_secret_keys or len(self.secret_key) < 32:
                raise ValueError("production requires a strong secret_key")
            if storage_provider == "local":
                raise ValueError("production requires object storage: set storage_provider=s3")
            if storage_provider == "s3":
                missing_storage = [
                    name
                    for name, value in {
                        "s3_bucket": self.s3_bucket,
                        "s3_private_bucket": self.s3_private_bucket,
                        "s3_access_key_id": self.s3_access_key_id,
                        "s3_secret_access_key": self.s3_secret_access_key,
                        "s3_public_base_url": self.s3_public_base_url,
                    }.items()
                    if not value
                ]
                if missing_storage:
                    raise ValueError(
                        "production s3 storage missing settings: "
                        + ", ".join(missing_storage)
                    )
                if self.s3_private_bucket == self.s3_bucket:
                    raise ValueError("production requires a separate private S3 bucket")
            if provider != "solapi":
                raise ValueError("production requires message_provider=solapi")
            if provider == "solapi":
                missing = [
                    name
                    for name, value in {
                        "solapi_api_key": self.solapi_api_key,
                        "solapi_api_secret": self.solapi_api_secret,
                        "solapi_sender_number": self.solapi_sender_number,
                        "solapi_webhook_secret": self.solapi_webhook_secret,
                    }.items()
                    if not value
                ]
                if missing:
                    raise ValueError(
                        "production solapi message provider missing settings: "
                        + ", ".join(missing)
                    )
                if not self.solapi_send_url.startswith("https://api.solapi.com/"):
                    raise ValueError("production requires the official HTTPS SOLAPI endpoint")
            if not self.sentry_dsn:
                raise ValueError("production requires sentry_dsn for error tracking")
            if not 0.0 <= self.sentry_traces_sample_rate <= 1.0:
                raise ValueError("sentry_traces_sample_rate must be in [0.0, 1.0]")


settings = Settings()
