from fastapi import APIRouter

from app.api.routes import auth, health, webhooks
from app.api.routes.admin import calendar, dashboard, messages, orders, partners, photos, reports, services
from app.api.routes.customer import orders as customer_orders
from app.api.routes.partner import jobs

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["admin-dashboard"])
api_router.include_router(calendar.router, prefix="/admin/calendar", tags=["admin-calendar"])
api_router.include_router(orders.router, prefix="/admin/orders", tags=["admin-orders"])
api_router.include_router(partners.router, prefix="/admin/partners", tags=["admin-partners"])
api_router.include_router(photos.router, prefix="/admin/photos", tags=["admin-photos"])
api_router.include_router(messages.router, prefix="/admin/messages", tags=["admin-messages"])
api_router.include_router(services.router, prefix="/admin/services", tags=["admin-services"])
api_router.include_router(reports.router, prefix="/admin/reports", tags=["admin-reports"])
api_router.include_router(jobs.router, prefix="/partner/jobs", tags=["partner-jobs"])
api_router.include_router(customer_orders.router, prefix="/customer/orders", tags=["customer-orders"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
