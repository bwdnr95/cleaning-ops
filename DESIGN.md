# Cleaning Ops Control Center Design System

## 1. Atmosphere & Identity

Cleaning Ops Control Center is a quiet operations command center. It should feel dense, fast, and trustworthy: tables and queues carry the work, while customer and partner views stay simple and reassuring. The signature is restrained operational clarity: white surfaces, cool neutral backgrounds, compact cards, small status colors, and clear next-action cues.

## 2. Color

### Palette

| Role | Token | Value | Usage |
|------|-------|-------|-------|
| Page/background | `--bg` | `#fafbfc` | Admin page background |
| Background/subtle | `--bg-subtle` | `#f4f6f8` | App frame, muted list rows |
| Background/muted | `--bg-muted` | `#eef1f4` | Hover, placeholder, count chips |
| Surface | `--surface` | `#ffffff` | Cards, tables, panels |
| Border/default | `--border` | `#e4e8ee` | Cards, dividers, inputs |
| Border/strong | `--border-strong` | `#d4d9e1` | Emphasized separators |
| Text/primary | `--text` | `#0f172a` | Main text |
| Text/secondary | `--text-secondary` | `#475569` | Supporting text |
| Text/tertiary | `--text-tertiary` | `#64748b` | Metadata |
| Text/quaternary | `--text-quaternary` | `#94a3b8` | Placeholder, quiet icons |
| Brand | `--brand` | `#4f46e5` | Primary actions, active nav |
| Brand/background | `--brand-bg` | `#eef2ff` | Brand chips, active row tint |
| On brand | `--on-brand` | `#ffffff` | Text/icons on solid brand controls |
| Info | `--info-fg` / `--info-bg` | `#1d4ed8` / `#eff6ff` | In progress, operational info |
| Warning | `--warn-fg` / `--warn-bg` | `#b45309` / `#fffbeb` | Waiting, attention |
| Success | `--success-fg` / `--success-bg` | `#047857` / `#ecfdf5` | Complete, visible, sent |
| Danger | `--danger-fg` / `--danger-bg` | `#b91c1c` / `#fef2f2` | Error, missed, blocked |
| Purple | `--purple-fg` / `--purple-bg` | `#6d28d9` / `#f5f3ff` | Customer confirmation, 상담 |
| Overlay | `--overlay-scrim` | `rgba(15, 23, 42, 0.38)` | Modal backdrop |

### Rules

Use status colors only to encode work state. Do not add decorative gradients or raw colors outside this table. Extend the table before adding a new semantic color.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| Page title | 18px | 600 | 1.35 | Admin dashboard greeting |
| Section title | 13px | 600 | 1.4 | Queue and card headers |
| Body | 12.5px | 400 to 600 | 1.45 | Tables, job rows |
| Body/sm | 11px to 11.5px | 400 to 600 | 1.35 | Metadata, labels |
| Caption | 10.5px | 500 to 700 | 1.3 | Time, chips, helper text |
| KPI number | 22px | 600 | 1.1 | Count cards |

### Font Stack

- Primary: system UI stack already used by the app.
- Mono: existing `.mono` utility for compact timestamps and IDs.

### Rules

Admin text stays compact. Customer and partner mobile screens may use larger body text, but inputs stay at least 16px on mobile to prevent iOS zoom.

## 4. Spacing & Layout

### Base Unit

All spacing follows a 4px base.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight icon gaps |
| `--space-2` | 8px | Row inner gaps |
| `--space-3` | 12px | Compact card padding |
| `--space-4` | 16px | Standard section gap |
| `--space-5` | 20px | Page padding |
| `--space-6` | 24px | Empty states, modal padding |

### Shared Control Tokens

| Role | Token | Value | Usage |
|------|-------|-------|-------|
| Compact control height | `--control-h-sm` | 34px | Dense desktop inputs and date cells |
| Touch target | `--touch-target` | 44px | Mobile buttons and interactive calendar cells |
| Pill radius | `--radius-pill` | 999px | Removable selected-date chips |
| Focus ring | `--focus-ring-width` / `--focus-ring-offset` | 2px / 2px | Keyboard focus on selected controls |
| Caption type | `--font-size-caption` | 10.5px | Weekday labels and compact metadata |
| Small body type | `--font-size-body-sm` | 11.5px | Chips and helper text |
| Body type | `--font-size-body` | 12.5px | Dense form controls |
| Section type | `--font-size-section` | 13px | Popover headings |

### Grid

- Admin content uses `.page-shell` and auto-fit grids.
- Customer reservation content uses a centered 768px maximum shell on larger screens.
- Dashboard KPI cards use `minmax(150px, 1fr)`.
- Work queue cards use `minmax(170px, 1fr)`.
- Split dashboard panels use `minmax(420px, 1fr)`.
- Mobile breakpoint is 768px.

### Rules

Dense admin layouts should remain scannable. Avoid nested cards and avoid page sections that look like decorative floating panels.

## 5. Components

### Work Queue Card

- Structure: button wrapping icon chip, count, title, description, and arrow icon.
- Variants: info, warn, danger, success, purple.
- Spacing: 12px padding, 8px inner vertical gap.
- States: default border, hover brand border with `--shadow-sm`, keyboard focus via existing button focus behavior.
- Accessibility: button must describe the destination through visible title and description.
- Motion: 100ms border and shadow transition only.

### Dashboard List Row

- Structure: full-width button row with compact metadata, main label, secondary label, and status badge.
- Variants: normal row, muted row.
- Spacing: 7px to 8px vertical padding, 10px column gap.
- States: clickable row, loading, error, empty via `DashMessage`.
- Accessibility: row click opens order detail or target queue.
- Motion: no layout animation.

### Status Badge

- Structure: compact inline badge with optional dot.
- Variants: info, warn, success, danger, purple, muted.
- Spacing: fit-content, no wrapping inside table rows.
- States: visible text must use customer/partner-safe wording outside admin-only pages.
- Accessibility: color never carries meaning alone.
- Motion: none.

### Multi Date Picker

- Structure: one compact trigger, a month grid that keeps the popover open while dates are toggled, selected-date chips, and explicit clear/today/done actions.
- Selection: consecutive and non-consecutive dates use the same toggle interaction; values are shown and submitted in ascending order.
- States: empty, one date, multiple dates, keyboard focus, selected day, and outside-month day.
- Spacing: 34px desktop trigger and day cells; all controls grow to the 44px touch target on mobile.
- Accessibility: the trigger exposes dialog state, every day uses `aria-pressed`, selected chips have named remove buttons, and changes are announced through `aria-live`.
- Motion: none. Month changes and selection are immediate so dense order entry remains predictable.

### Brand Logo Lockup

- Structure: the official `cleanjob-logo.png` inside a dark `--text` frame, with optional compact caption.
- Sizes: small for admin sidebar and partner app bars, medium for customer headers, large for login panels.
- Usage: admin, customer, and partner entry points should all show the same logo treatment so external links read as official Cleanjob surfaces.
- Accessibility: image alt is `클린잡`; captions describe the surface such as `운영 시스템`, `예약 확인센터`, or `협력사 작업센터`.
- Motion: none.

### Customer Aftercare Action

- Structure: customer-safe status copy, one primary action, and an inline memo form inside the reservation line card.
- States: available, form open, submitting, validation error, pending admin review, and accepted/in progress.
- Spacing: 16px outer padding, 8px control gap, 12px between copy and action.
- Colors: available uses neutral surface tokens, pending uses warning tokens, and accepted uses info tokens.
- Accessibility: textarea has a visible label, errors are inline with `role="alert"`, and submission status uses `aria-live="polite"`.
- Motion: no automatic motion; only the existing 100ms button feedback is allowed.

## 6. Motion & Interaction

| Type | Duration | Usage |
|------|----------|-------|
| Micro | 100ms | Card hover border and shadow |
| Standard | 150ms to 200ms | Drawer or modal transitions if already present |

Only animate opacity, transform, border-color, or shadow. Hover must communicate clickability or state, not decorate.

## 7. Depth & Surface

### Strategy

Mixed, but restrained: borders define most surfaces and shadows appear only on hover, popovers, modals, and framed preview shells.

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-xs` | `0 1px 2px rgba(15,23,42,0.04)` | Inputs |
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)` | Cards, hover |
| `--shadow-md` | `0 4px 12px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)` | Popovers |
| `--shadow-lg` | `0 12px 32px rgba(15,23,42,0.08), 0 2px 6px rgba(15,23,42,0.04)` | Modals |

Cards use 8px or smaller radius unless the existing component already requires otherwise.
