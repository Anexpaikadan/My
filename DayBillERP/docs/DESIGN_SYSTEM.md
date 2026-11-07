# DayBill 8 — design system

Figma source: **[DayBill ERP — Redesign v8](https://www.figma.com/design/bnHMQhG6oq5TAqa0ddEkYn)**
(pages: Foundations · Components · Screens). Figma uses Inter as a stand-in; the
app uses Segoe UI on Windows.

## Colour tokens → `config/settings.py` THEMES["daybill"]

| Figma variable | Theme key | Value |
|---|---|---|
| brand/primary | `primary`, `info`, `select_bg`, `sidebar_active` | `#2952E3` |
| brand/primary-hover | `primary_dark` | `#1F43C7` |
| brand/primary-soft | `primary_light` | `#EDF2FF` |
| sidebar/bg | `sidebar_bg` | `#0B1220` |
| sidebar/hover | `sidebar_hover` | `#162036` |
| sidebar/text | `sidebar_text` | `#E6EAF2` |
| sidebar/muted | `sidebar_muted` | `#8B95A9` |
| sidebar/field | `sidebar_field` | `#131C2E` |
| surface/page | `content_bg` | `#F4F6FA` |
| surface/card · surface/topbar | `card_bg`, `topbar_bg` | `#FFFFFF` |
| surface/heading | `heading_bg` | `#F7F9FC` |
| text/primary | `text_primary` | `#0F172A` |
| text/secondary | `text_secondary` | `#5B6475` |
| border/default | `border` | `#E3E8EF` |
| border/field | `field_border` | `#D0D7E2` |
| status/success · warning · danger | `success`, `warning`, `danger` | `#12A15E` · `#D97706` · `#E5484D` |
| tile/blue · green · orange · purple | `tile_*` | `#2952E3` · `#12B76A` · `#F79009` · `#7A5AF8` |

For text, `success` and `warning` are darker than the Figma status colours so
they stay readable on white.

## Components → Tk

| Figma component | In the app |
|---|---|
| Button / Primary · Secondary · Ghost · Danger | `TButton` · `Secondary.TButton` · `Ghost.TButton` · `Danger.TButton` (`ui/ui_kit.py`), padding 16 × 8 |
| Input | Tk `Entry` / `TEntry` / `TCombobox`: flat, 1 px `field_border`, focus = `primary`, padding 10 × 7 |
| Nav Item (Default / Active) | side menu rows in `ui/main_window.py` |
| KPI Tile | `DashboardView._kpi_card` (`ui/dashboard.py`) |
| Table head / rows | `Treeview` rowheight 32, heading on `heading_bg`, muted bold text |

Shell sizes: side menu 236 px, top bar 52 px, taskbar 34 px.

## Screens (v8.1)

| Figma screen | Code |
|---|---|
| Sales Invoice | `InvoiceForm._build_window`, `_build_form_header`, `_build_totals_bar`, `_build_footer` (`ui/invoices.py`); header blocks in `ui/doc_header.py`; grid in `ui/invoice_grid.py` |
| POS | `POSWindow._build` (`ui/pos.py`); colours from `_pos_palette()`; buttons `_pbtn`, fields `_pfield` |
