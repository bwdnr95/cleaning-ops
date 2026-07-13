from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from app.services.day_before_scheduler import day_before_notice_lifespan
from app.services.recurring_scheduler import recurring_order_lifespan


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(recurring_order_lifespan(app))
        await stack.enter_async_context(day_before_notice_lifespan(app))
        yield
