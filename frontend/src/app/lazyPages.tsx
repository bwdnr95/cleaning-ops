import React from 'react';

export const CalendarPage = React.lazy(() => import('../features/admin/calendar/CalendarPage').then((module) => ({ default: module.CalendarPage })));
export const Dashboard = React.lazy(() => import('../features/admin/dashboard/Dashboard').then((module) => ({ default: module.Dashboard })));
export const MessagesPage = React.lazy(() => import('../features/admin/messages/MessagesPage').then((module) => ({ default: module.MessagesPage })));
export const OrderDetailPage = React.lazy(() => import('../features/admin/orders/OrderDetailPage').then((module) => ({ default: module.OrderDetailPage })));
export const OrderFormPage = React.lazy(() => import('../features/admin/orders/OrderFormPage').then((module) => ({ default: module.OrderFormPage })));
export const OrdersPage = React.lazy(() => import('../features/admin/orders/OrdersPage').then((module) => ({ default: module.OrdersPage })));
export const BrokersPage = React.lazy(() => import('../features/admin/brokers/BrokersPage').then((module) => ({ default: module.BrokersPage })));
export const PartnersPage = React.lazy(() => import('../features/admin/partners/PartnersPage').then((module) => ({ default: module.PartnersPage })));
export const PhotoReviewPage = React.lazy(() => import('../features/admin/photo-review/PhotoReviewPage').then((module) => ({ default: module.PhotoReviewPage })));
export const ProductsPage = React.lazy(() => import('../features/admin/products/ProductsPage').then((module) => ({ default: module.ProductsPage })));
export const RecurringContractsPage = React.lazy(() => import('../features/admin/recurring/RecurringContractsPage').then((module) => ({ default: module.RecurringContractsPage })));
export const ReportsPage = React.lazy(() => import('../features/admin/reports/ReportsPage').then((module) => ({ default: module.ReportsPage })));
export const CustomerReservation = React.lazy(() => import('../features/customer/CustomerReservation').then((module) => ({ default: module.CustomerReservation })));
export const PartnerApp = React.lazy(() => import('../features/partner/PartnerApp').then((module) => ({ default: module.PartnerApp })));
