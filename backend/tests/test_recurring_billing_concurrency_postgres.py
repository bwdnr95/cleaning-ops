from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from runpy import run_path
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.time import business_today
from app.domain.constants import (
    OrderStatus,
    RecurrenceMode,
    RecurringBillingMode,
    RecurringContractStatus,
    UserRole,
)
from app.domain.customer_token import generate_customer_token
from app.domain.payment_status import PartnerPaymentStatus
from app.models.order import Order
from app.models.order_group import OrderGroup
from app.models.partner import Partner
from app.models.recurring_contract import RecurringContract
from app.models.recurring_monthly_status import RecurringMonthlyStatus
from app.models.recurring_partner_billing_period import RecurringPartnerBillingPeriod
from app.models.user import User
from app.repositories.partners import PartnerRepository
from app.repositories.recurring import RecurringContractRepository
from app.schemas.order import OrderGroupUpdate, OrderUpdate
from app.schemas.partner import PartnerUpdate
from app.schemas.recurring import RecurringContractUpdate
from app.services.orders import OrderService
from app.services.partner_settlements import PartnerSettlementService
from app.services.partners import PartnerService
from app.services.recurring import RecurringService
from app.services.recurring_generation import (
    GenerationWindow,
    RecurringOrderGenerationService,
)
from app.services.recurring_monthly import RecurringMonthlyService
from app.services.recurring_partner_billing import BASELINE_EFFECTIVE_MONTH, billing_month
from app.services.reports import ReportService

POSTGRES_URL = os.getenv("POSTGRES_CONCURRENCY_DATABASE_URL")

# 이 테스트들은 대상 DB에 시드 데이터를 커밋하고 정리하지 않는다.
# 2026-08-17 실운영 DB(cleaning_ops)를 향해 실행되어 '동시성 계약' 36건이
# 운영 화면에 노출된 사고가 있었다 → DB 이름에 test/rehearsal/throwaway가
# 없으면 일회용 DB가 아니라고 보고 실행을 거부한다.
_DISPOSABLE_DB_MARKERS = ("test", "rehearsal", "throwaway", "scratch")
if POSTGRES_URL:
    _db_name = (make_url(POSTGRES_URL).database or "").lower()
    if not any(marker in _db_name for marker in _DISPOSABLE_DB_MARKERS):
        raise RuntimeError(
            "POSTGRES_CONCURRENCY_DATABASE_URL must point to a disposable database "
            f"(name containing one of {_DISPOSABLE_DB_MARKERS}), got: {_db_name!r}. "
            "These tests commit seed rows without cleanup — never run them against "
            "an operational database."
        )

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="POSTGRES_CONCURRENCY_DATABASE_URL is required for row-lock tests",
)


@dataclass(frozen=True)
class BillingCase:
    partner_id: str
    contract_id: str
    order_id: str
    month: str


@pytest.fixture
def postgres_sessions():
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield engine, factory
    finally:
        engine.dispose()


def _seed_case(
    factory: sessionmaker[Session],
    *,
    mode: RecurringBillingMode,
    amount: int,
    partner_prefix: str = "partner",
    with_monthly_status: bool = False,
    order_status: OrderStatus = OrderStatus.SCHEDULED,
) -> BillingCase:
    suffix = uuid4().hex
    today = business_today()
    month = billing_month(today)
    partner_id = f"{partner_prefix}-{suffix}"[:36]
    group_id = f"group-{suffix}"[:36]
    contract_id = f"contract-{suffix}"[:36]
    order_id = f"order-{suffix}"[:36]
    with factory() as db:
        partner = Partner(
            id=partner_id,
            name=f"동시성 협력사 {suffix[:8]}",
            phone=f"010{suffix[:8]}",
            is_active=True,
        )
        group = OrderGroup(
            id=group_id,
            customer_token=generate_customer_token(),
            customer_name="동시성 고객",
            customer_phone="01011112222",
            customer_address="서울시 동시성로 1",
            customer_visible_payment=False,
        )
        contract = RecurringContract(
            id=contract_id,
            label=f"동시성 계약 {suffix[:8]}",
            order_group_id=group_id,
            recurrence_mode=RecurrenceMode.MONTHLY,
            day_of_month=today.day,
            start_date=today.replace(day=1),
            status=RecurringContractStatus.ACTIVE,
            default_partner_id=partner_id,
            service_name="정기청소",
            partner_billing_mode=mode,
            partner_payment_amount=amount,
        )
        order = Order(
            id=order_id,
            group_id=group_id,
            status=order_status,
            received_date=today,
            scheduled_date=today,
            partner_id=partner_id,
            service_name="정기청소",
            partner_payment_amount=(
                amount if mode == RecurringBillingMode.PER_VISIT else None
            ),
            partner_payment_status=(
                PartnerPaymentStatus.UNPAID
                if mode == RecurringBillingMode.PER_VISIT
                else None
            ),
            recurring_contract_id=contract_id,
            recurring_planned_date=today,
        )
        period = RecurringPartnerBillingPeriod(
            contract_id=contract_id,
            effective_month=BASELINE_EFFECTIVE_MONTH,
            partner_id=partner_id,
            billing_mode=mode,
            partner_payment_amount=amount,
        )
        db.add_all([partner, group])
        db.flush()
        db.add_all([contract, period])
        db.flush()
        db.add(order)
        if with_monthly_status:
            db.add(
                RecurringMonthlyStatus(
                    id=str(uuid4()),
                    contract_id=contract_id,
                    billing_month=month,
                    partner_payment_paid=False,
                )
            )
        db.commit()
    return BillingCase(partner_id, contract_id, order_id, month)


def _wait_for_database_lock(engine, backend_pid: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            wait_event_type = connection.scalar(
                text(
                    "SELECT wait_event_type FROM pg_stat_activity "
                    "WHERE pid = :backend_pid"
                ),
                {"backend_pid": backend_pid},
            )
        if wait_event_type == "Lock":
            return
        time.sleep(0.05)
    raise AssertionError(f"backend {backend_pid} did not wait on a database lock")


def _wait_for_application_pid(engine, *, database_name: str, application_name: str) -> int:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            backend_pid = connection.scalar(
                text(
                    "SELECT pid FROM pg_stat_activity "
                    "WHERE datname = :database_name AND application_name = :application_name "
                    "ORDER BY backend_start DESC LIMIT 1"
                ),
                {
                    "database_name": database_name,
                    "application_name": application_name,
                },
            )
        if backend_pid is not None:
            return int(backend_pid)
        time.sleep(0.05)
    raise AssertionError(f"application {application_name} did not connect")


def test_mode_change_commits_before_settlement_rechecks_order(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as changing:
        partner = PartnerRepository(changing).get_for_update(case.partner_id)
        assert partner is not None
        locked = RecurringContractRepository(changing).get_for_update(case.contract_id)
        assert locked is not None

        def settle() -> None:
            with factory() as settling:
                pid.put(int(settling.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    PartnerSettlementService(settling).settle(
                        partner_id=case.partner_id,
                        order_ids=[case.order_id],
                        actor_user_id=None,
                    )
                    settling.commit()
                    result.put("settled")
                except ValueError as exc:
                    settling.rollback()
                    result.put(str(exc))

        worker = Thread(target=settle, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        RecurringService(changing).update_contract(
            case.contract_id,
            RecurringContractUpdate(
                partner_billing_mode=RecurringBillingMode.MONTHLY,
                partner_payment_amount=250000,
            ),
            actor_user_id=None,
        )
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "invalid_settlement_order"
    with factory() as verify:
        order = verify.get(Order, case.order_id)
        assert order is not None
        assert order.partner_payment_amount is None
        assert order.partner_payment_status is None


def test_settlement_commits_before_mode_change_preserves_paid_order(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as settling:
        PartnerSettlementService(settling).settle(
            partner_id=case.partner_id,
            order_ids=[case.order_id],
            actor_user_id=None,
        )

        def change_mode() -> None:
            with factory() as changing:
                pid.put(int(changing.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    RecurringService(changing).update_contract(
                        case.contract_id,
                        RecurringContractUpdate(
                            partner_billing_mode=RecurringBillingMode.MONTHLY,
                            partner_payment_amount=250000,
                        ),
                        actor_user_id=None,
                    )
                    result.put("changed")
                except ValueError as exc:
                    changing.rollback()
                    result.put(str(exc))

        worker = Thread(target=change_mode, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        settling.commit()
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "changed"
    with factory() as verify:
        order = verify.get(Order, case.order_id)
        contract = verify.get(RecurringContract, case.contract_id)
        assert order is not None
        assert order.partner_payment_status == PartnerPaymentStatus.PAID
        assert order.partner_settled_at is not None
        assert order.partner_payment_amount == 70000
        assert contract is not None
        assert contract.partner_billing_mode == RecurringBillingMode.MONTHLY


def test_monthly_to_per_visit_preserves_locked_monthly_obligation(
    postgres_sessions,
) -> None:
    _engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        order_status=OrderStatus.COMPLETED,
    )

    with factory() as changing:
        RecurringService(changing).update_contract(
            case.contract_id,
            RecurringContractUpdate(
                partner_billing_mode=RecurringBillingMode.PER_VISIT,
                partner_payment_amount=70000,
            ),
            actor_user_id=None,
        )

    with factory() as verify:
        order = verify.get(Order, case.order_id)
        status = verify.scalar(
            select(RecurringMonthlyStatus).where(
                RecurringMonthlyStatus.contract_id == case.contract_id,
                RecurringMonthlyStatus.billing_month == case.month,
            )
        )
        retained = next(
            row
            for row in ReportService(verify).settlements().rows
            if row.order_id == f"recurring-monthly:{case.contract_id}:{case.month}"
        )
        assert order is not None
        assert order.partner_payment_amount is None
        assert order.partner_payment_status is None
        assert status is not None
        assert status.retained_partner_id == case.partner_id
        assert status.retained_partner_payment_amount == 250000
        assert retained.partner_id == case.partner_id
        assert retained.expected_settlement_amount == 250000


def test_group_edit_and_mode_change_share_canonical_lock_order(
    postgres_sessions,
) -> None:
    _engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    ready: Queue[str] = Queue()
    result: Queue[str] = Queue()

    def edit_group() -> None:
        with factory() as editing:
            ready.put("edit")
            try:
                OrderService(editing).update_with_group(
                    case.order_id,
                    OrderUpdate(special_request="동시 수정"),
                    OrderGroupUpdate(customer_name="잠금 순서 고객"),
                    actor_user_id=None,
                )
                result.put("edit:ok")
            except Exception as exc:
                editing.rollback()
                result.put(f"edit:{type(exc).__name__}")

    def change_mode() -> None:
        with factory() as changing:
            ready.put("mode")
            try:
                RecurringService(changing).update_contract(
                    case.contract_id,
                    RecurringContractUpdate(
                        partner_billing_mode=RecurringBillingMode.MONTHLY,
                        partner_payment_amount=250000,
                    ),
                    actor_user_id=None,
                )
                result.put("mode:ok")
            except Exception as exc:
                changing.rollback()
                result.put(f"mode:{type(exc).__name__}")

    workers = [
        Thread(target=edit_group, daemon=True),
        Thread(target=change_mode, daemon=True),
    ]
    for worker in workers:
        worker.start()
    assert {ready.get(timeout=5), ready.get(timeout=5)} == {"edit", "mode"}
    for worker in workers:
        worker.join(timeout=10)
        assert not worker.is_alive()

    assert {result.get(timeout=1), result.get(timeout=1)} == {"edit:ok", "mode:ok"}
    with factory() as verify:
        order = verify.get(Order, case.order_id)
        group = verify.get(OrderGroup, order.group_id if order is not None else "")
        assert order is not None
        assert group is not None
        assert order.customer_name == "잠금 순서 고객"
        assert group.customer_name == "잠금 순서 고객"


def test_mode_change_serializes_monthly_payment_and_rejects_stale_toggle(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        with_monthly_status=True,
    )
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as changing:
        partner = PartnerRepository(changing).get_for_update(case.partner_id)
        assert partner is not None
        locked = RecurringContractRepository(changing).get_for_update(case.contract_id)
        assert locked is not None

        def pay_month() -> None:
            with factory() as paying:
                pid.put(int(paying.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    RecurringMonthlyService(paying).set_status(
                        case.contract_id,
                        case.month,
                        partner_payment_paid=True,
                    )
                    result.put("paid")
                except ValueError as exc:
                    paying.rollback()
                    result.put(str(exc))

        worker = Thread(target=pay_month, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        RecurringService(changing).update_contract(
            case.contract_id,
            RecurringContractUpdate(
                partner_billing_mode=RecurringBillingMode.PER_VISIT,
                partner_payment_amount=70000,
            ),
            actor_user_id=None,
        )
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "recurring_partner_payment_not_monthly"
    with factory() as verify:
        status = verify.scalar(
            select(RecurringMonthlyStatus).where(
                RecurringMonthlyStatus.contract_id == case.contract_id,
                RecurringMonthlyStatus.billing_month == case.month,
            )
        )
        assert status is not None
        assert status.partner_payment_paid is False


def test_mode_change_commits_before_generation_uses_refreshed_terms(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    with factory() as setup:
        order = setup.get(Order, case.order_id)
        assert order is not None
        setup.delete(order)
        setup.add(
            RecurringPartnerBillingPeriod(
                contract_id=case.contract_id,
                effective_month=case.month,
                partner_id=case.partner_id,
                billing_mode=RecurringBillingMode.PER_VISIT,
                partner_payment_amount=70000,
            )
        )
        setup.commit()
    result: Queue[int | str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as changing:
        partner = PartnerRepository(changing).get_for_update(case.partner_id)
        assert partner is not None
        contract = RecurringContractRepository(changing).get_for_update(case.contract_id)
        assert contract is not None

        def generate() -> None:
            with factory() as generating:
                retained_period = generating.get(
                    RecurringPartnerBillingPeriod,
                    (case.contract_id, case.month),
                )
                assert retained_period is not None
                pid.put(int(generating.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    generated_contract = generating.get(
                        RecurringContract,
                        case.contract_id,
                    )
                    assert generated_contract is not None
                    created = RecurringOrderGenerationService(
                        generating
                    ).generate_current_month_for_contract(
                        generated_contract,
                        actor_user_id=None,
                    )
                    result.put(created)
                except ValueError as exc:
                    generating.rollback()
                    result.put(str(exc))

        worker = Thread(target=generate, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        RecurringService(changing).update_contract(
            case.contract_id,
            RecurringContractUpdate(
                partner_billing_mode=RecurringBillingMode.MONTHLY,
                partner_payment_amount=250000,
            ),
            actor_user_id=None,
        )
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == 1
    with factory() as verify:
        orders = list(
            verify.scalars(
                select(Order).where(Order.recurring_contract_id == case.contract_id)
            )
        )
        assert len(orders) == 1
        assert orders[0].partner_payment_amount is None
        assert orders[0].partner_payment_status is None


def test_generation_commits_before_mode_change_normalizes_new_order(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    with factory() as setup:
        order = setup.get(Order, case.order_id)
        assert order is not None
        setup.delete(order)
        setup.commit()
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()
    today = business_today()

    with factory() as generating:
        contract = generating.get(RecurringContract, case.contract_id)
        assert contract is not None
        created = RecurringOrderGenerationService(generating)._generate_contract_month(
            contract,
            GenerationWindow(first=today, last=today),
            actor_user_id=None,
        )
        assert created == 1

        def change_mode() -> None:
            with factory() as changing:
                pid.put(int(changing.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    RecurringService(changing).update_contract(
                        case.contract_id,
                        RecurringContractUpdate(
                            partner_billing_mode=RecurringBillingMode.MONTHLY,
                            partner_payment_amount=250000,
                        ),
                        actor_user_id=None,
                    )
                    result.put("changed")
                except ValueError as exc:
                    changing.rollback()
                    result.put(str(exc))

        worker = Thread(target=change_mode, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        generating.commit()
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "changed"
    with factory() as verify:
        order = verify.scalar(
            select(Order).where(Order.recurring_contract_id == case.contract_id)
        )
        assert order is not None
        assert order.partner_payment_amount is None
        assert order.partner_payment_status is None


def test_generation_batch_releases_locks_before_next_contract(
    postgres_sessions,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _engine, factory = postgres_sessions
    first_case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
        partner_prefix="zz-partner",
    )
    second_case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
        partner_prefix="aa-partner",
    )
    entered_second_contract = Event()
    release_second_contract = Event()
    update_completed = Event()
    results: Queue[str] = Queue()
    today = business_today()

    def generate_batch() -> None:
        with factory() as generating:
            service = RecurringOrderGenerationService(generating)
            first_contract = generating.get(RecurringContract, first_case.contract_id)
            second_contract = generating.get(RecurringContract, second_case.contract_id)
            assert first_contract is not None and second_contract is not None
            monkeypatch.setattr(
                service.contracts,
                "list_active",
                lambda: [first_contract, second_contract],
            )
            generate_contract_month = service._generate_contract_month

            def gated_generate(
                contract: RecurringContract,
                window: GenerationWindow,
                *,
                actor_user_id: str | None,
            ) -> int:
                if contract.id == second_case.contract_id:
                    entered_second_contract.set()
                    if not release_second_contract.wait(timeout=10):
                        raise AssertionError("second contract gate timed out")
                return generate_contract_month(
                    contract,
                    window,
                    actor_user_id=actor_user_id,
                )

            monkeypatch.setattr(service, "_generate_contract_month", gated_generate)
            try:
                created = service.generate_month(
                    today,
                    today,
                    actor_user_id=None,
                )
                results.put(f"generate:{created}")
            except (SQLAlchemyError, ValueError, AssertionError) as exc:
                generating.rollback()
                results.put(f"generate:{type(exc).__name__}")

    def update_first_contract() -> None:
        with factory() as updating:
            try:
                RecurringService(updating).update_contract(
                    first_case.contract_id,
                    RecurringContractUpdate(
                        default_partner_id=second_case.partner_id,
                    ),
                    actor_user_id=None,
                )
                results.put("update:ok")
            except (SQLAlchemyError, ValueError) as exc:
                updating.rollback()
                results.put(f"update:{type(exc).__name__}")
            finally:
                update_completed.set()

    generator = Thread(target=generate_batch, daemon=True)
    updater = Thread(target=update_first_contract, daemon=True)
    generator.start()
    if not entered_second_contract.wait(timeout=5):
        release_second_contract.set()
        generator.join(timeout=5)
        raise AssertionError("generation did not reach the second contract")
    updater.start()
    completed_before_second_contract = update_completed.wait(timeout=5)
    release_second_contract.set()
    updater.join(timeout=10)
    generator.join(timeout=10)

    assert completed_before_second_contract
    assert not updater.is_alive()
    assert not generator.is_alive()
    assert {results.get(timeout=1), results.get(timeout=1)} == {
        "generate:0",
        "update:ok",
    }


def test_settlement_revert_commits_before_archive_rechecks_unpaid_order(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
        order_status=OrderStatus.COMPLETED,
    )
    with factory() as setup:
        contract = setup.get(RecurringContract, case.contract_id)
        assert contract is not None
        PartnerSettlementService(setup).settle(
            partner_id=case.partner_id,
            order_ids=[case.order_id],
            actor_user_id=None,
        )
        contract.status = RecurringContractStatus.PAUSED
        setup.commit()
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as reverting:
        PartnerSettlementService(reverting).revert(
            partner_id=case.partner_id,
            order_ids=[case.order_id],
            actor_user_id=None,
        )

        def archive() -> None:
            with factory() as archiving:
                pid.put(int(archiving.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    PartnerService(archiving).delete(case.partner_id)
                    result.put("archived")
                except ValueError as exc:
                    archiving.rollback()
                    result.put(str(exc))

        worker = Thread(target=archive, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        reverting.commit()
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "partner_has_unpaid_settlements"
    with factory() as verify:
        partner = verify.get(Partner, case.partner_id)
        assert partner is not None
        assert partner.deleted_at is None


def test_archive_commit_blocks_monthly_payment_reopen(postgres_sessions) -> None:
    _engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        with_monthly_status=True,
        order_status=OrderStatus.COMPLETED,
    )
    with factory() as setup:
        contract = setup.get(RecurringContract, case.contract_id)
        status = setup.scalar(
            select(RecurringMonthlyStatus).where(
                RecurringMonthlyStatus.contract_id == case.contract_id,
                RecurringMonthlyStatus.billing_month == case.month,
            )
        )
        assert contract is not None and status is not None
        contract.status = RecurringContractStatus.PAUSED
        status.partner_payment_paid = True
        setup.commit()
    with factory() as archiving:
        PartnerService(archiving).delete(case.partner_id)

    with factory() as reopening:
        with pytest.raises(ValueError, match="partner_not_found"):
            RecurringMonthlyService(reopening).set_status(
                case.contract_id,
                case.month,
                partner_payment_paid=False,
            )


def test_archive_and_pause_serialize_before_monthly_debt_materialization(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        order_status=OrderStatus.COMPLETED,
    )
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as archiving:
        partner = PartnerRepository(archiving).get_for_update(case.partner_id)
        assert partner is not None

        def pause() -> None:
            with factory() as pausing:
                pid.put(int(pausing.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    RecurringService(pausing).set_status(
                        case.contract_id,
                        RecurringContractStatus.PAUSED,
                    )
                    result.put("paused")
                except ValueError as exc:
                    pausing.rollback()
                    result.put(str(exc))

        worker = Thread(target=pause, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        with pytest.raises(
            ValueError,
            match="partner_has_(unpaid_settlements|recurring_contracts)",
        ):
            PartnerService(archiving).delete(case.partner_id)
        archiving.rollback()
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "paused"
    with factory() as verify:
        partner = verify.get(Partner, case.partner_id)
        contract = verify.get(RecurringContract, case.contract_id)
        status = verify.scalar(
            select(RecurringMonthlyStatus).where(
                RecurringMonthlyStatus.contract_id == case.contract_id,
                RecurringMonthlyStatus.billing_month == case.month,
            )
        )
        assert partner is not None and partner.deleted_at is None
        assert contract is not None and contract.status == RecurringContractStatus.PAUSED
        assert status is not None and status.partner_payment_paid is False


def test_pause_commit_makes_waiting_archive_recheck_monthly_debt(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        order_status=OrderStatus.COMPLETED,
    )
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as pausing:
        partner = PartnerRepository(pausing).get_for_update(case.partner_id)
        assert partner is not None
        contract = RecurringContractRepository(pausing).get_for_update(case.contract_id)
        assert contract is not None

        def archive() -> None:
            with factory() as archiving:
                pid.put(int(archiving.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    PartnerService(archiving).delete(case.partner_id)
                    result.put("archived")
                except ValueError as exc:
                    archiving.rollback()
                    result.put(str(exc))

        worker = Thread(target=archive, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        RecurringService(pausing).set_status(
            case.contract_id,
            RecurringContractStatus.PAUSED,
        )
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "partner_has_unpaid_settlements"
    with factory() as verify:
        partner = verify.get(Partner, case.partner_id)
        assert partner is not None and partner.deleted_at is None


def test_archive_commit_blocks_concurrent_partner_reactivation(postgres_sessions) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
        order_status=OrderStatus.COMPLETED,
    )
    with factory() as setup:
        order = setup.get(Order, case.order_id)
        contract = setup.get(RecurringContract, case.contract_id)
        partner = setup.get(Partner, case.partner_id)
        assert order is not None and contract is not None and partner is not None
        setup.delete(order)
        contract.status = RecurringContractStatus.PAUSED
        partner.is_active = False
        setup.add(
            User(
                id=f"user-{uuid4().hex}"[:36],
                role=UserRole.PARTNER,
                name="동시성 협력사 계정",
                email=None,
                phone=f"010{uuid4().hex[:8]}",
                password_hash="test-hash",
                partner_id=case.partner_id,
                is_active=False,
            )
        )
        setup.commit()
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as archiving:
        partner = PartnerRepository(archiving).get_for_update(case.partner_id)
        assert partner is not None

        def activate() -> None:
            with factory() as updating:
                pid.put(int(updating.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    PartnerService(updating).update(
                        case.partner_id,
                        PartnerUpdate(is_active=True),
                    )
                    result.put("activated")
                except ValueError as exc:
                    updating.rollback()
                    result.put(str(exc))

        worker = Thread(target=activate, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        PartnerService(archiving).delete(case.partner_id)
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "partner_not_found"
    with factory() as verify:
        partner = verify.get(Partner, case.partner_id)
        assert partner is not None
        assert partner.deleted_at is not None
        assert partner.is_active is False
        user = verify.scalar(select(User).where(User.partner_id == case.partner_id))
        assert user is not None and user.is_active is False


def test_archive_commit_blocks_admin_settlement_reopen(postgres_sessions) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
        order_status=OrderStatus.COMPLETED,
    )
    with factory() as setup:
        contract = setup.get(RecurringContract, case.contract_id)
        assert contract is not None
        PartnerSettlementService(setup).settle(
            partner_id=case.partner_id,
            order_ids=[case.order_id],
            actor_user_id=None,
        )
        contract.status = RecurringContractStatus.PAUSED
        setup.commit()

    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()
    with factory() as archiving:
        partner = PartnerRepository(archiving).get_for_update(case.partner_id)
        assert partner is not None

        def reopen() -> None:
            with factory() as updating:
                pid.put(int(updating.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    OrderService(updating).update(
                        case.order_id,
                        OrderUpdate(
                            partner_payment_status=PartnerPaymentStatus.UNPAID,
                        ),
                        actor_user_id=None,
                    )
                    result.put("reopened")
                except ValueError as exc:
                    updating.rollback()
                    result.put(str(exc))

        worker = Thread(target=reopen, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        PartnerService(archiving).delete(case.partner_id)
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "partner_not_found"
    with factory() as verify:
        partner = verify.get(Partner, case.partner_id)
        order = verify.get(Order, case.order_id)
        assert partner is not None and partner.deleted_at is not None
        assert order is not None
        assert order.partner_payment_status == PartnerPaymentStatus.PAID
        assert order.partner_settled_at is not None


def test_archived_actual_order_partner_history_is_not_rewritten(
    postgres_sessions,
) -> None:
    _engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
        order_status=OrderStatus.COMPLETED,
    )
    archived_partner_id = f"archived-{uuid4().hex}"[:36]
    with factory() as setup:
        archived_partner = Partner(
            id=archived_partner_id,
            name="수동 재배정 협력사",
            phone=f"010{uuid4().hex[:8]}",
            is_active=True,
        )
        setup.add(archived_partner)
        setup.flush()
        order = setup.get(Order, case.order_id)
        assert order is not None
        order.partner_id = archived_partner_id
        setup.commit()

    with factory() as archiving:
        PartnerService(archiving).delete(archived_partner_id)

    with factory() as changing:
        RecurringService(changing).update_contract(
            case.contract_id,
            RecurringContractUpdate(
                partner_billing_mode=RecurringBillingMode.PER_VISIT,
                partner_payment_amount=70000,
            ),
            actor_user_id=None,
        )

    with factory() as verify:
        contract = verify.get(RecurringContract, case.contract_id)
        order = verify.get(Order, case.order_id)
        partner = verify.get(Partner, archived_partner_id)
        assert contract is not None
        assert contract.partner_billing_mode == RecurringBillingMode.PER_VISIT
        assert order is not None
        assert order.partner_id == archived_partner_id
        assert order.partner_payment_amount is None
        assert order.partner_payment_status is None
        assert partner is not None and partner.deleted_at is not None


def test_partner_assignment_commits_before_archive_rechecks_active_contract(
    postgres_sessions,
) -> None:
    engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.PER_VISIT,
        amount=70000,
    )
    with factory() as setup:
        order = setup.get(Order, case.order_id)
        contract = setup.get(RecurringContract, case.contract_id)
        period = setup.get(
            RecurringPartnerBillingPeriod,
            (case.contract_id, BASELINE_EFFECTIVE_MONTH),
        )
        assert order is not None and contract is not None and period is not None
        setup.delete(order)
        contract.default_partner_id = None
        period.partner_id = None
        setup.commit()
    result: Queue[str] = Queue()
    pid: Queue[int] = Queue()

    with factory() as assigning:
        partner = PartnerRepository(assigning).get_for_update(case.partner_id)
        assert partner is not None

        def archive() -> None:
            with factory() as archiving:
                pid.put(int(archiving.scalar(text("SELECT pg_backend_pid()"))))
                try:
                    PartnerService(archiving).delete(case.partner_id)
                    result.put("archived")
                except ValueError as exc:
                    archiving.rollback()
                    result.put(str(exc))

        worker = Thread(target=archive, daemon=True)
        worker.start()
        _wait_for_database_lock(engine, pid.get(timeout=5))
        RecurringService(assigning).update_contract(
            case.contract_id,
            RecurringContractUpdate(default_partner_id=case.partner_id),
            actor_user_id=None,
        )
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert result.get(timeout=1) == "partner_has_recurring_contracts"


def test_admin_order_update_rejects_monthly_per_order_payment(postgres_sessions) -> None:
    _engine, factory = postgres_sessions
    case = _seed_case(
        factory,
        mode=RecurringBillingMode.MONTHLY,
        amount=250000,
    )

    with factory() as updating:
        with pytest.raises(ValueError, match="recurring_partner_payment_not_per_visit"):
            OrderService(updating).update(
                case.order_id,
                OrderUpdate(partner_payment_status=PartnerPaymentStatus.PAID),
                actor_user_id=None,
            )
        updating.rollback()

    with factory() as verify:
        order = verify.get(Order, case.order_id)
        assert order is not None
        assert order.partner_payment_amount is None
        assert order.partner_payment_status is None


def test_downgrade_lock_blocks_history_insert_until_transaction_finishes(
    postgres_sessions,
) -> None:
    engine, _factory = postgres_sessions
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0031_partner_archive_and_recurring_billing_periods.py"
    )
    namespace = run_path(str(migration_path))
    schema = f"migration_race_{uuid4().hex}"
    with engine.begin() as setup:
        setup.execute(text(f'CREATE SCHEMA "{schema}"'))
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".partners '
                "(id varchar(36) PRIMARY KEY, deleted_at timestamptz NULL)"
            )
        )
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".recurring_partner_billing_periods '
                "(contract_id varchar(36), effective_month varchar(7), "
                "PRIMARY KEY (contract_id, effective_month))"
            )
        )
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".recurring_contracts '
                "(id varchar(36) PRIMARY KEY, start_date date NOT NULL, "
                "active_segment_start_date date NULL, status varchar(20) NOT NULL "
                "DEFAULT 'active', deleted_at timestamptz NULL)"
            )
        )
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".orders '
                "(id varchar(36) PRIMARY KEY, "
                "recurring_partner_settlement_retained boolean NOT NULL DEFAULT false)"
            )
        )
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".recurring_monthly_status '
                "(id varchar(36) PRIMARY KEY, "
                "retained_partner_payment_amount numeric(12,2) NULL)"
            )
        )
    pid: Queue[int] = Queue()
    result: Queue[str] = Queue()

    try:
        with engine.connect() as locking:
            transaction = locking.begin()
            locking.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            namespace["lock_downgrade_state"](locking)
            namespace["ensure_downgrade_preserves_billing_history"](locking)

            def insert_history() -> None:
                with engine.begin() as inserting:
                    inserting.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    pid.put(int(inserting.scalar(text("SELECT pg_backend_pid()"))))
                    inserting.execute(
                        text(
                            "INSERT INTO recurring_partner_billing_periods "
                            "(contract_id, effective_month) VALUES ('contract-1', '2026-08')"
                        )
                    )
                    result.put("inserted")

            worker = Thread(target=insert_history, daemon=True)
            worker.start()
            _wait_for_database_lock(engine, pid.get(timeout=5))
            transaction.rollback()
            worker.join(timeout=5)
            assert not worker.is_alive()

        assert result.get(timeout=1) == "inserted"
        with engine.connect() as verify:
            count = verify.scalar(
                text(
                    f'SELECT count(*) FROM "{schema}".'
                    "recurring_partner_billing_periods"
                )
            )
            assert count == 1
    finally:
        with engine.begin() as cleanup:
            cleanup.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_order_visit_downgrade_lock_blocks_concurrent_visit_insert(
    postgres_sessions,
) -> None:
    engine, _factory = postgres_sessions
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0032_order_visit_dates.py"
    )
    namespace = run_path(str(migration_path))
    schema = f"order_visit_migration_race_{uuid4().hex}"
    with engine.begin() as setup:
        setup.execute(text(f'CREATE SCHEMA "{schema}"'))
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".orders '
                "(id varchar(36) PRIMARY KEY, scheduled_date date NULL)"
            )
        )
        setup.execute(
            text(
                f'CREATE TABLE "{schema}".order_visits '
                "(id varchar(36) PRIMARY KEY, order_id varchar(36) NOT NULL, "
                "visit_date date NOT NULL, UNIQUE (order_id, visit_date))"
            )
        )
        setup.execute(
            text(
                f'INSERT INTO "{schema}".orders (id, scheduled_date) '
                "VALUES ('order-1', DATE '2026-08-17')"
            )
        )
        setup.execute(
            text(
                f'INSERT INTO "{schema}".order_visits (id, order_id, visit_date) '
                "VALUES ('visit-1', 'order-1', DATE '2026-08-17')"
            )
        )
    pid: Queue[int] = Queue()
    result: Queue[str] = Queue()

    try:
        with engine.connect() as locking:
            transaction = locking.begin()
            locking.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            namespace["lock_downgrade_state"](locking)
            namespace["_ensure_downgrade_is_representable"](locking)

            def insert_visit() -> None:
                with engine.begin() as inserting:
                    inserting.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    pid.put(int(inserting.scalar(text("SELECT pg_backend_pid()"))))
                    inserting.execute(
                        text(
                            "INSERT INTO order_visits (id, order_id, visit_date) "
                            "VALUES ('visit-2', 'order-1', DATE '2026-08-19')"
                        )
                    )
                    result.put("inserted")

            worker = Thread(target=insert_visit, daemon=True)
            worker.start()
            _wait_for_database_lock(engine, pid.get(timeout=5))
            transaction.rollback()
            worker.join(timeout=5)
            assert not worker.is_alive()

        assert result.get(timeout=1) == "inserted"
        with engine.connect() as verify:
            count = verify.scalar(
                text(f'SELECT count(*) FROM "{schema}".order_visits')
            )
            assert count == 2
    finally:
        with engine.begin() as cleanup:
            cleanup.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.mark.parametrize("legacy_lock_order", ["order_first", "message_first"])
def test_split_visit_migrations_avoid_legacy_lock_cycles(
    postgres_sessions,
    legacy_lock_order: str,
) -> None:
    _engine, _factory = postgres_sessions
    assert POSTGRES_URL is not None
    base_url = make_url(POSTGRES_URL)
    database_name = f"gate_mv_split_{uuid4().hex}"
    application_name = f"mv-split-{uuid4().hex}"
    admin_engine = create_engine(
        base_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    case_url = base_url.set(database=database_name)
    migration_url = case_url.update_query_dict({"application_name": application_name})
    backend_dir = Path(__file__).parents[1]
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = migration_url.render_as_string(
        hide_password=False
    )

    with admin_engine.connect() as admin:
        admin.execute(text(f'CREATE DATABASE "{database_name}"'))
    case_engine = create_engine(case_url)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "upgrade",
                "0031_partner_billing_periods",
            ],
            cwd=backend_dir,
            env=migration_environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        with case_engine.begin() as setup:
            setup.execute(
                text(
                    "INSERT INTO order_groups "
                    "(id, customer_token, customer_name, customer_phone, "
                    "customer_address, customer_visible_payment) VALUES "
                    "('group-probe', 'probe-token', '고객', '01012345678', '서울', false)"
                )
            )
            setup.execute(
                text(
                    "INSERT INTO orders "
                    "(id, group_id, status, received_date, scheduled_date, service_name, "
                    "discount_amount, as_requested, as_intake_pending, "
                    "recurring_partner_settlement_retained) VALUES "
                    "('order-probe', 'group-probe', '일정확정', DATE '2026-08-17', "
                    "DATE '2026-08-18', '입주청소', 0, false, false, false)"
                )
            )
            setup.execute(
                text(
                    "INSERT INTO message_logs "
                    "(id, order_id, recipient_type, recipient_name, recipient_phone, "
                    "message_type, channel, content, status) VALUES "
                    "('message-probe', 'order-probe', 'customer', '고객', '01012345678', "
                    "'customer_day_before', 'sms', 'legacy', 'pending')"
                )
            )

        migration_result: Queue[subprocess.CompletedProcess[str]] = Queue()

        def run_upgrade() -> None:
            migration_result.put(
                subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=backend_dir,
                    env=migration_environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            )

        with case_engine.connect() as legacy:
            transaction = legacy.begin()
            if legacy_lock_order == "order_first":
                legacy.execute(
                    text(
                        "UPDATE orders SET status = '전날안내필요', "
                        "scheduled_date = DATE '2026-08-25' "
                        "WHERE id = 'order-probe'"
                    )
                )
            else:
                legacy.execute(
                    text("SELECT id FROM message_logs WHERE id = 'message-probe'")
                )

            worker = Thread(target=run_upgrade, daemon=True)
            worker.start()
            migration_pid = _wait_for_application_pid(
                admin_engine,
                database_name=database_name,
                application_name=application_name,
            )
            _wait_for_database_lock(admin_engine, migration_pid)

            if legacy_lock_order == "order_first":
                legacy.execute(
                    text(
                        "UPDATE message_logs SET status = 'sent' "
                        "WHERE id = 'message-probe'"
                    )
                )
            else:
                legacy.execute(
                    text("SELECT id FROM orders WHERE id = 'order-probe' FOR UPDATE")
                )
                legacy.execute(
                    text(
                        "UPDATE orders SET status = '전날안내필요', "
                        "scheduled_date = DATE '2026-08-25' "
                        "WHERE id = 'order-probe'"
                    )
                )
                legacy.execute(
                    text(
                        "UPDATE message_logs SET status = 'sent' "
                        "WHERE id = 'message-probe'"
                    )
                )
            legacy.execute(
                text(
                    "INSERT INTO orders "
                    "(id, group_id, status, received_date, scheduled_date, service_name, "
                    "discount_amount, as_requested, as_intake_pending, "
                    "recurring_partner_settlement_retained) VALUES "
                    "('order-gap', 'group-probe', '일정확정', DATE '2026-08-17', "
                    "DATE '2026-08-26', '정기청소', 0, false, false, false)"
                )
            )
            transaction.commit()
            worker.join(timeout=30)
            assert not worker.is_alive()

        completed = migration_result.get(timeout=1)
        assert completed.returncode == 0, completed.stderr
        with case_engine.connect() as verify:
            revision = verify.scalar(text("SELECT version_num FROM alembic_version"))
            visit_rows = verify.execute(
                text(
                    "SELECT orders.id, orders.scheduled_date::text, "
                    "order_visits.visit_date::text "
                    "FROM orders LEFT JOIN order_visits "
                    "ON order_visits.order_id = orders.id "
                    "WHERE orders.id IN ('order-gap', 'order-probe') "
                    "ORDER BY orders.id"
                )
            ).all()
            has_target_column = verify.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'message_logs' "
                    "AND column_name = 'target_visit_date')"
                )
            )
        assert revision == "0033_day_before_target_visit_date"
        assert visit_rows == [
            ("order-gap", "2026-08-26", "2026-08-26"),
            ("order-probe", "2026-08-25", "2026-08-25"),
        ]
        assert has_target_column is True

        with case_engine.begin() as current_app:
            current_app.execute(
                text(
                    "UPDATE orders SET scheduled_date = DATE '2026-09-02' "
                    "WHERE id = 'order-probe'"
                )
            )
            current_app.execute(
                text("DELETE FROM order_visits WHERE order_id = 'order-probe'")
            )
            current_app.execute(
                text(
                    "INSERT INTO order_visits (id, order_id, visit_date) VALUES "
                    "('current-visit-1', 'order-probe', DATE '2026-09-02'), "
                    "('current-visit-2', 'order-probe', DATE '2026-09-07')"
                )
            )
        with case_engine.connect() as verify:
            current_visit_dates = verify.scalars(
                text(
                    "SELECT visit_date::text FROM order_visits "
                    "WHERE order_id = 'order-probe' ORDER BY visit_date"
                )
            ).all()
        assert current_visit_dates == ["2026-09-02", "2026-09-07"]

        with pytest.raises(
            SQLAlchemyError,
            match="visit_dates_required_for_multi_visit_order",
        ):
            with case_engine.begin() as legacy_multi_update:
                legacy_multi_update.execute(
                    text(
                        "UPDATE orders SET scheduled_date = DATE '2026-09-05' "
                        "WHERE id = 'order-probe'"
                    )
                )
        with case_engine.connect() as verify:
            preserved_schedule = verify.scalar(
                text(
                    "SELECT scheduled_date::text FROM orders "
                    "WHERE id = 'order-probe'"
                )
            )
            preserved_visit_dates = verify.scalars(
                text(
                    "SELECT visit_date::text FROM order_visits "
                    "WHERE order_id = 'order-probe' ORDER BY visit_date"
                )
            ).all()
        assert preserved_schedule == "2026-09-02"
        assert preserved_visit_dates == ["2026-09-02", "2026-09-07"]
    finally:
        case_engine.dispose()
        with admin_engine.connect() as admin:
            admin.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            admin.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()
