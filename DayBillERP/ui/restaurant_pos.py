# ============================================================
# DayBill ERP - the POS for restaurants (v7.0)
# ------------------------------------------------------------
# Built into the POS window ONLY when the company uses the Restaurant
# module (business.has("restaurant")); otherwise the POS is unchanged.
#
# A strip under the customer line shows the order on the screen:
#   order type (Dine-in / Takeaway / Delivery), table, guests, waiter,
#   delivery customer, items the kitchen does not have yet, and the
#   buttons Tables · Note · Service · Send to Kitchen · Print Bill.
#
#   F4   Send to Kitchen (KOT) — only what is new or changed
#   F5   Print Bill (before payment; the table shows "bill printed")
#   F6   Hold = keep the order on its table (every PC sees it)
#   F7   Running orders — open one
#   F11  Kitchen note for the selected line ("no onion")
#   F12  Tables
#   Cash / Card / Save   pay: a normal POS bill is written, the order is
#                        closed and the table is free again
#
# The running order is kept in rest_orders / rest_order_lines
# (modules/restaurant.py). Two PCs on one order: both changes are kept.
# ============================================================

import tkinter as tk
from tkinter import messagebox

from config import settings as cfg
from config.database import db
from modules import restaurant as R

BG, FG, MUTED = "#2A1E3F", "#FFFFFF", "#C9B8E8"
ON, OFF = "#E67E22", "#4A3A63"


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


class RestaurantBar:
    def __init__(self, pos):
        if not R.ready():                       # database not updated yet: plain POS
            raise RuntimeError("the restaurant tables are not in this database yet")
        self.pos = pos
        self.order = None            # the running order on the screen (dict)
        self.version = None          # its version when this screen loaded / saved it
        self.base = []               # its items at that moment (to join changes)
        self.base_sig = ()
        self.pending_type = self.default_type()
        self.service_on = True
        self._svc_ids = set()
        self._paid = None
        self._refresh_job = None
        self._build()
        self._bind()
        self.refresh()

    # ── look ─────────────────────────────────────────────────
    def _build(self):
        pos = self.pos
        bar = self.frame = tk.Frame(pos.win, bg=BG)
        after = getattr(pos, "_cust_strip", None)
        if after is not None:
            bar.pack(fill="x", after=after)
        else:
            bar.pack(fill="x")
        tk.Label(bar, text="🍽", font=("Segoe UI Emoji", 13), bg=BG, fg=FG).pack(side="left", padx=(10, 4))
        self.title_var = tk.StringVar()
        self.title_lbl = tk.Label(bar, textvariable=self.title_var, font=("Segoe UI", 11, "bold"),
                                  bg=BG, fg=FG, cursor="hand2")
        self.title_lbl.pack(side="left")
        self.title_lbl.bind("<Button-1>", lambda e: self.edit_details())
        tk.Button(bar, text="✎", font=("Segoe UI", 10, "bold"), bg=OFF, fg=FG, relief="flat",
                  cursor="hand2", command=self.edit_details, width=2).pack(side="left", padx=(6, 10))
        self.type_btns = {}
        for t in R.order_types():
            b = tk.Button(bar, text=t, font=("Segoe UI", 10, "bold"), relief="flat", fg=FG, bg=OFF,
                          padx=10, cursor="hand2", command=lambda tt=t: self.choose_type(tt))
            b.pack(side="left", padx=2, pady=4, ipady=2)
            self.type_btns[t] = b
        self.unsent_var = tk.StringVar()
        self.unsent_lbl = tk.Label(bar, textvariable=self.unsent_var, font=("Segoe UI", 10, "bold"),
                                   bg=BG, fg="#F8C471")
        self.unsent_lbl.pack(side="left", padx=12)
        right = tk.Frame(bar, bg=BG)
        right.pack(side="right", padx=6)

        def btn(text, bg, cmd):
            b = tk.Button(right, text=text, font=("Segoe UI", 10, "bold"), bg=bg, fg=FG, relief="flat",
                          padx=10, cursor="hand2", activebackground=bg, activeforeground=FG,
                          command=cmd)
            b.pack(side="left", padx=2, pady=4, ipady=3)
            return b
        btn("🍽 Tables  F12", "#5B4B8A", self.tables)
        btn("📝 Note  F11", "#5B4B8A", lambda: self.note())
        self.svc_btn = btn("Service", "#5B4B8A", self.toggle_service)
        self.kot_btn = btn("🍳 Send to Kitchen  F4", "#D35400", self.send_kot)
        btn("🧾 Print Bill  F5", "#7D3C98", self.print_bill)
        try:
            pos._shrink(bar)
        except Exception:
            pass

    def _bind(self):
        w = self.pos.win
        w.bind("<F4>", lambda e: (self.send_kot(), "break")[1])
        w.bind("<F5>", lambda e: (self.print_bill(), "break")[1])
        w.bind("<F11>", lambda e: (self.note(), "break")[1])
        w.bind("<F12>", lambda e: (self.tables(), "break")[1])

    def status(self, text):
        try:
            self.pos.status_var.set(text)
        except Exception:
            pass

    # ── state ────────────────────────────────────────────────
    @staticmethod
    def default_type():
        types = R.order_types()
        if "Takeaway" in types:
            return "Takeaway"
        rest = [t for t in types if t != "Dine-in"]
        return rest[0] if rest else types[0]

    def cur_type(self):
        return (self.order or {}).get("order_type") or self.pending_type

    def order_id(self):
        return (self.order or {}).get("order_id")

    def items(self, lines=None):
        return [ln for ln in (self.pos.cart if lines is None else lines) if not ln.get("_service")]

    def _incl(self):
        try:
            return bool(self.pos.incl_vat_var.get())
        except Exception:
            return str(cfg.get("sales_price_tax_mode", "inclusive")).lower() == "inclusive"

    @staticmethod
    def _sig(lines):
        return tuple(sorted((str(R.line_key(ln)), round(_f(ln.get("quantity")), 3),
                             round(_f(ln.get("unit_price")), 4)) for ln in lines
                            if not ln.get("_service")))

    def dirty(self):
        return self._sig(self.pos.cart) != self.base_sig

    def _set_base(self, lines):
        self.base = [dict(ln) for ln in self.items(lines)]
        self.base_sig = self._sig(self.base)

    def to_cart(self, rows):
        """Saved order lines → POS bill lines."""
        incl = self._incl()
        out = []
        for r in rows:
            price = _f(r.get("unit_price"))
            rate = _f(r.get("vat_rate"))
            was = bool(r.get("price_incl", True))
            if was != incl and rate:                    # Settings changed in between
                price = price / (1 + rate / 100.0) if was else price * (1 + rate / 100.0)
            ln = {"product_id": r.get("product_id"), "product_code": r.get("product_code") or "",
                  "product_name_en": r.get("product_name_en") or "",
                  "product_name_ar": r.get("product_name_ar") or "",
                  "unit_name": r.get("unit_name") or "Unit", "factor": _f(r.get("factor")) or 1.0,
                  "unit_price": round(price, 4), "quantity": _f(r.get("quantity")),
                  "_base_price": round(price, 4), "vat_rate": rate,
                  "vat_code": r.get("vat_code") or "S", "vat_category_id": r.get("vat_category_id"),
                  "note": r.get("kitchen_note") or ""}
            if r.get("price_typed"):
                ln.update(_price_typed=True, offer_off=True)
            self.pos._recalc(ln)
            out.append(ln)
        return out

    def attach(self, order, rows=None, keep_cart=False):
        """Put an order on the screen (its saved items, or keep_cart=True:
        the items already on the screen become this order's items)."""
        pos = self.pos
        self.order = dict(order)
        self.version = order.get("version")
        self.service_on = bool(order.get("service_on", True))
        self._svc_ids = set()
        if keep_cart:
            self.base, self.base_sig = [], ()
        else:
            pos.cart = self.to_cart(rows or [])
            self._set_base(pos.cart)
        pos._sel_idx = None
        pos._render_cart()
        self.refresh()

    def detach(self, clear=True):
        pos = self.pos
        self.order = None
        self.version = None
        self.base, self.base_sig = [], ()
        self.pending_type = self.default_type()
        self.service_on = True
        self._svc_ids = set()
        if clear:
            pos.cart = []
            pos._sel_idx = None
            try:
                pos.paid_var.set("0.00")
            except Exception:
                pass
            pos._render_cart()
        self.refresh()

    def _notify(self):
        try:
            from ui import restaurant as UR
            UR.changed()
        except Exception:
            pass

    # ── strip ────────────────────────────────────────────────
    def schedule_refresh(self):
        try:
            if self._refresh_job:
                self.pos.win.after_cancel(self._refresh_job)
            self._refresh_job = self.pos.win.after(250, self.refresh)
        except Exception:
            self.refresh()

    def refresh(self):
        self._refresh_job = None
        o = self.order
        t = self.cur_type()
        if o:
            txt = R.summary(o, short=True)
            if o.get("status") == "billed":
                txt += "  ·  BILL PRINTED"
        else:
            txt = "New order  ·  %s" % t
        try:
            self.title_var.set(txt)
            for name, b in self.type_btns.items():
                b.configure(bg=ON if name == t else OFF)
            pct = R.service_pct()
            if pct > 0 and t == "Dine-in":
                self.svc_btn.configure(text=("Service %g%% ✓" % pct) if self.service_on
                                       else "Service off", bg="#1E8449" if self.service_on else "#5B4B8A")
                if not self.svc_btn.winfo_ismapped():
                    self.svc_btn.pack(side="left", padx=2, pady=4, ipady=3, before=self.kot_btn)
            elif self.svc_btn.winfo_ismapped():
                self.svc_btn.pack_forget()
        except Exception:
            pass
        n = 0
        try:
            if self.items():
                n = R.unsent_count(self.order_id(), self.items())
        except Exception:
            n = 0
        try:
            if n:
                self.unsent_var.set("🍳 %d not sent to kitchen" % n)
                self.unsent_lbl.configure(fg="#F8C471")
            elif self.order and self.items():
                self.unsent_var.set("✓ kitchen has every item")
                self.unsent_lbl.configure(fg="#82E0AA")
            else:
                self.unsent_var.set("")
        except Exception:
            pass

    # ── service charge (dine-in) ─────────────────────────────
    def sync_service(self):
        """Called before the POS draws the bill: the service charge line
        (one per VAT rate, VAT added on it) follows the dine-in items."""
        pos = self.pos
        cart = pos.cart
        pct = R.service_pct()
        sale = [ln for ln in cart if not ln.get("_service") and _f(ln.get("quantity")) > 0]
        present = {id(ln) for ln in cart if ln.get("_service")}
        want = pct > 0 and self.cur_type() == "Dine-in" and self.service_on and bool(sale)
        if want and self._svc_ids and not (self._svc_ids & present):
            # the cashier took the line off → no service charge on this order
            self.service_on = False
            want = False
            if self.order:
                try:
                    R.update_order(self.order_id(), service_on=0)
                except Exception:
                    pass
            self.status("Service charge taken off this bill (press 'Service' to add it back).")
        if present:
            cart[:] = [ln for ln in cart if not ln.get("_service")]
        self._svc_ids = set()
        if want:
            vat_on = cfg.flag("vat_enabled", True) and cfg.flag("apply_vat_pos", True)
            incl = self._incl()
            groups = {}
            for ln in sale:
                k = (_f(ln.get("vat_rate")), ln.get("vat_code") or "S", ln.get("vat_category_id"))
                groups[k] = groups.get(k, 0.0) + _f(ln.get("taxable"))
            for (rate, code, cat), net in groups.items():
                amt = round(net * pct / 100.0, 2)
                if amt <= 0:
                    continue
                price = amt * (1 + rate / 100.0) if (incl and vat_on and rate) else amt
                ln = {"product_id": None, "product_code": "", "product_name_en":
                      "Service charge %g%%" % pct + (("  (%s %g%%)" % ("VAT", rate)) if len(groups) > 1 else ""),
                      "product_name_ar": "رسوم الخدمة", "unit_name": "Service", "factor": 1.0,
                      "unit_price": round(price, 4), "quantity": 1, "vat_rate": rate, "vat_code": code,
                      "vat_category_id": cat, "_service": True, "offer_off": True, "_price_typed": True}
                pos._recalc(ln)
                cart.append(ln)
                self._svc_ids.add(id(ln))
        self.schedule_refresh()

    def toggle_service(self):
        self.service_on = not self.service_on
        if self.order:
            try:
                R.update_order(self.order_id(), service_on=self.service_on)
            except Exception:
                pass
        self._svc_ids = set()
        self.pos._render_cart()
        self.status("Service charge %s for this order." % ("ON" if self.service_on else "OFF"))

    # ── saving the order ─────────────────────────────────────
    def ensure_order(self):
        """The order on the screen; makes one (the chosen type) when the
        screen has none. → order_id or None (cancelled)."""
        if self.order:
            return self.order_id()
        t = self.pending_type
        if t == "Dine-in":
            return self.start_table()
        if t == "Delivery":
            return self.start_order("Delivery")
        return self.start_order(t)

    def save(self, quiet=False):
        """Keep the items on the screen in the order (every PC sees them).
        → True when saved."""
        pos = self.pos
        oid = self.ensure_order()
        if not oid:
            return False
        lines = self.items()
        try:
            total = pos._bill_parts()["net"]
        except Exception:
            total = None
        try:
            v = R.save_lines(oid, lines, self.version, self._incl(), total)
            merged = False
        except R.OrderChanged:
            theirs = self.to_cart(R.order_lines(oid))
            lines = R.merge_lines(self.base, lines, theirs)
            o = R.get_order(oid) or {}
            v = R.save_lines(oid, lines, o.get("version"), self._incl(), None)
            self._svc_ids = set()
            pos.cart = lines
            pos._sel_idx = None
            pos._render_cart()
            merged = True
        except R.OrderClosed as e:
            messagebox.showwarning("Order", "%s\n\nThe items stay on the screen as a new bill." % e,
                                   parent=pos.win)
            self.detach(clear=False)
            return False
        except ValueError as e:
            messagebox.showwarning("Order", str(e), parent=pos.win)
            return False
        self.version = v
        self.order = R.get_order(oid) or self.order
        self._set_base(pos.cart)
        if merged:
            self.status("This order was also changed on another computer — both changes are kept.")
        elif not quiet:
            self.status("Order %s saved." % R.summary(self.order, short=True))
        self._notify()
        self.refresh()
        return True

    def _empty_order(self):
        """No items and the kitchen has nothing: the order can just go."""
        return not self.items() and not R.sent_map(self.order_id())

    def leave(self, on_close=False):
        """Before the screen moves to another bill: the order on it is
        saved (an empty one is dropped and its table is free again).
        → False when the user wants to stay."""
        pos = self.pos
        if self.order:
            try:
                if self._empty_order():
                    R.cancel(self.order_id(), "Nothing ordered")
                    self._notify()
                elif self.dirty() and not self.save(quiet=True):
                    if self.order:
                        return False
            except R.OrderClosed:
                pass
            if self.order:
                self.detach()
                return True
        if not pos.cart or on_close or pos._loaded_invoice_id:
            return True
        ans = messagebox.askyesnocancel(
            "Items on the screen",
            "The items on the screen are not saved.\n\nYes = keep them as a %s order\n"
            "No = clear them\nCancel = go back" % self.pending_type, parent=pos.win)
        if ans is None:
            return False
        if ans:
            if not self.save(quiet=True):
                return False
            self.detach()
            return True
        try:
            from modules import cashier_watch as _cw
            _cw.log_void("clear", list(self.items()))
        except Exception:
            pass
        self.detach()
        return True

    def hold(self):
        """F6 — keep the order (table / takeaway / delivery) and clear the
        screen. → True when handled here."""
        if not self.pos.cart and not self.order:
            return False
        if self.order and self._empty_order():
            R.cancel(self.order_id(), "Nothing ordered")
            self.detach()
            self._notify()
            self.status("Nothing was ordered — the order is removed.")
            return True
        if not self.save(quiet=True):
            return True
        what = R.summary(self.order, short=True)
        self.detach()
        self.status("%s is kept. Open it again with Running orders (F7) or Tables (F12)." % what)
        try:
            self.pos.barcode_entry.focus_set()
        except Exception:
            pass
        return True

    # ── opening orders ───────────────────────────────────────
    def _front(self):
        try:
            w = self.pos.win
            if w.state() in ("iconic", "withdrawn"):
                w.deiconify()
            w.lift()
            w.focus_force()
            self.pos.barcode_entry.focus_set()
        except Exception:
            pass

    def open_order(self, order_id):
        """Show a running order on the POS (the order on the screen is
        saved first)."""
        if self.order and self.order_id() == int(order_id):
            self._front()
            return True
        if not self.leave():
            return False
        o = R.get_order(order_id)
        if not o or o.get("status") not in R.RUNNING:
            messagebox.showinfo("Order", "This order is already paid or cancelled.", parent=self.pos.win)
            self._notify()
            return False
        self.pos._new_sale(ask=False)
        self.attach(o, R.order_lines(order_id))
        self.status("Opened %s — add items, Send to Kitchen (F4), Print Bill (F5) or take payment."
                    % R.summary(o, short=True))
        self._front()
        return True

    def start_table(self, table_id=None, guests=None, waiter=None):
        """A new dine-in order on a free table. The items already on the
        screen (not an order yet) go on it. → order_id or None."""
        if not table_id:
            from ui import restaurant as UR
            got = UR.pick_table(self.pos.win, free_only=True)
            if not got:
                return None
            table_id, guests, waiter = got
        if self.order and not self.leave():
            return None
        if self.pos._loaded_invoice_id:
            self.pos._new_sale(ask=False)
        try:
            oid = R.open_order("Dine-in", table_id, guests=guests, waiter=waiter)
        except ValueError as e:
            messagebox.showwarning("Table", str(e), parent=self.pos.win)
            return None
        keep = bool(self.pos.cart)
        self.attach(R.get_order(oid), [], keep_cart=keep)
        if keep:
            self.save(quiet=True)
        self._notify()
        self.status("New order on %s." % R.summary(self.order, short=True))
        self._front()
        return oid

    def start_order(self, order_type, **details):
        """A new takeaway / delivery order (delivery asks the customer
        details when they are not given). → order_id or None."""
        if order_type == "Delivery" and not details:
            from ui import restaurant as UR
            details = UR.ask_delivery(self.pos.win)
            if details is None:
                return None
        if self.order and not self.leave():
            return None
        if self.pos._loaded_invoice_id:
            self.pos._new_sale(ask=False)
        try:
            oid = R.open_order(order_type, None, **details)
        except ValueError as e:
            messagebox.showwarning("Order", str(e), parent=self.pos.win)
            return None
        keep = bool(self.pos.cart)
        self.attach(R.get_order(oid), [], keep_cart=keep)
        if keep:
            self.save(quiet=True)
        self._notify()
        self._front()
        return oid

    def choose_type(self, order_type, table_id=None, guests=None, waiter=None, details=None):
        """The order type buttons of the strip."""
        pos = self.pos
        if order_type == self.cur_type() and order_type == "Takeaway":
            return True
        if order_type == "Dine-in":
            if self.order and self.order.get("table_id") and not table_id:
                return True
            if not table_id:
                from ui import restaurant as UR
                got = UR.pick_table(pos.win, free_only=True)
                if not got:
                    return False
                table_id, guests, waiter = got
            if not self.order:
                return bool(self.start_table(table_id, guests, waiter))
            try:
                R.set_type(self.order_id(), "Dine-in", table_id)
                R.update_order(self.order_id(), **{k: v for k, v in (("guests", guests),
                                                                      ("waiter_name", waiter)) if v})
            except (ValueError, R.OrderClosed) as e:
                messagebox.showwarning("Table", str(e), parent=pos.win)
                return False
        elif order_type == "Delivery":
            if details is None:
                from ui import restaurant as UR
                details = UR.ask_delivery(pos.win, self.order)
                if details is None:
                    return False
            if not self.order:
                return bool(self.start_order("Delivery", **details))
            try:
                R.set_type(self.order_id(), "Delivery")
                R.update_order(self.order_id(), customer_name=details.get("customer_name"),
                               customer_phone=details.get("phone"),
                               delivery_address=details.get("address"),
                               driver_name=details.get("driver"))
            except (ValueError, R.OrderClosed) as e:
                messagebox.showwarning("Order", str(e), parent=pos.win)
                return False
        else:
            if not self.order:
                self.pending_type = order_type
                pos._render_cart()
                self.refresh()
                return True
            try:
                R.set_type(self.order_id(), order_type)
            except (ValueError, R.OrderClosed) as e:
                messagebox.showwarning("Order", str(e), parent=pos.win)
                return False
        o = R.get_order(self.order_id())
        if o:
            self.order = o
            self.version = o.get("version")         # this screen made the change
        pos._render_cart()
        self._notify()
        self.status("Order is now %s." % R.summary(self.order, short=True))
        return True

    def edit_details(self):
        """✎ guests, waiter, delivery customer / driver."""
        if not self.order:
            if not self.pos.cart:
                self.status("Pick a table (F12) or an order type first.")
                return
            if not self.ensure_order():
                return
        from ui import restaurant as UR
        got = UR.ask_details(self.pos.win, self.order)
        if not got:
            return
        R.update_order(self.order_id(), **got)
        self.order = R.get_order(self.order_id()) or self.order
        self._notify()
        self.refresh()

    def tables(self):
        """F12 — the tables: a free one starts an order, a busy one opens."""
        from ui import restaurant as UR
        UR.TablePicker(self.pos.win, self)

    def retrieve(self):
        """F7 — running orders."""
        from ui import restaurant as UR
        UR.RunningOrders(self.pos.win, self)
        return True

    # ── kitchen note ─────────────────────────────────────────
    def note(self, text=None, count=None):
        """F11 — a note for the kitchen on the selected line. count = for
        how many of the line (the rest stay without the note)."""
        pos = self.pos
        idx = pos._pad_line()
        if idx is None:
            self.status("Add an item first, then write its note.")
            return False
        ln = pos.cart[idx]
        if ln.get("_service") or _f(ln.get("quantity")) <= 0:
            self.status("A note is for an item the kitchen makes.")
            return False
        qty = _f(ln.get("quantity"))
        if text is None:
            from ui import restaurant as UR
            got = UR.ask_note(pos.win, ln.get("note") or "", qty, R.note_choices(),
                              ln.get("product_name_en") or "")
            if got is None:
                return False
            text, count = got
        text = str(text or "").strip()[:200]
        if count and 0 < count < qty - 1e-9:
            ln["quantity"] = round(qty - count, 3)
            pos._recalc(ln)
            new = dict(ln, quantity=float(count), note=text)
            for k in ("taxable", "vat_amount", "line_total", "discount_amount", "offer_id", "offer_text"):
                new.pop(k, None)
            pos._recalc(new)
            pos.cart.insert(idx + 1, new)
            pos._render_cart(select_line=new)
        else:
            ln["note"] = text
            pos._render_cart(select_line=ln)
        self.status(("Note: %s" % text) if text else "Note removed.")
        return True

    # ── kitchen tickets ──────────────────────────────────────
    def print_kots(self, kot_ids):
        if not kot_ids or not R.flag("rest_kot_print"):
            return
        for kid in kot_ids:
            try:
                ok, msg = R.print_kot(kid)
            except Exception as e:
                ok, msg = False, "KOT not printed: %s" % str(e)[:120]
            self.status(msg)

    def send_kot(self):
        """F4 — send what the kitchen does not have yet."""
        pos = self.pos
        if not self.items() and not self.order:
            self.status("Add items first, then Send to Kitchen.")
            return []
        if not self.save(quiet=True):
            return []
        oid = self.order_id()
        try:
            ids = R.send_to_kitchen(oid, self.items())
        except Exception as e:
            messagebox.showerror("Kitchen", "The kitchen ticket was not made.\n\n%s" % str(e)[:300],
                                 parent=pos.win)
            return []
        if not ids:
            self.status("The kitchen already has every item of this order.")
            self.refresh()
            return []
        self.print_kots(ids)
        ks = [R.kot(k) for k in ids]
        txt = "🍳 Sent to kitchen: " + ", ".join("KOT %s (%s)" % (k["kot_no"], k["station_name"])
                                               for k in ks if k)
        self._notify()
        if self.cur_type() == "Dine-in" and R.flag("rest_clear_after_kot"):
            what = R.summary(self.order, short=True)
            self.detach()
            txt += "  ·  %s is saved — pick the next table (F12)." % what
        else:
            self.refresh()
        self.status(txt)
        return ids

    # ── the bill before payment ──────────────────────────────
    def bill_totals(self):
        P = self.pos._bill_parts()
        return {"net": round(P["s_gross"] - P["r_gross"], 2), "vat": round(P["s_vat"] - P["r_vat"], 2),
                "total": round(P["net"], 2)}

    def print_bill(self, send_first=None):
        """F5 — print the bill for the guest (not a tax invoice); the table
        shows 'bill printed' until it is paid."""
        pos = self.pos
        from modules import permissions as _pm
        if not _pm.allowed("pos", "print", parent=pos.win):
            return None
        if not pos.cart:
            pos._empty_bill_msg()
            return None
        if not self.save(quiet=True):
            return None
        oid = self.order_id()
        n = R.unsent_count(oid, self.items())
        if n:
            if send_first is None:
                send_first = messagebox.askyesno(
                    "Kitchen", "%d item(s) are not sent to the kitchen yet.\nSend them now?" % n,
                    parent=pos.win)
            if send_first:
                ids = R.send_to_kitchen(oid, self.items())
                self.print_kots(ids)
        totals = self.bill_totals()
        lines = [dict(ln) for ln in pos.cart]
        path = None
        try:
            path = R.prebill_pdf(self.order, lines, totals)
            from ui.print_menu import send_pdf
            send_pdf(pos.win, path, "Bill #%s" % self.order.get("order_no"), printer_key="pos")
        except Exception as e:
            self.status("Bill not printed: %s" % str(e)[:120])
        R.mark_billed(oid, totals["total"])
        self.order = R.get_order(oid) or self.order
        self._notify()
        self.refresh()
        self.status("🧾 Bill printed for %s — %s. Take the payment with Cash / Card."
                    % (R.summary(self.order, short=True), R.money(totals["total"])))
        return path

    # ── Delete Bill ──────────────────────────────────────────
    def delete_bill(self, ask=True, reason="Cancelled at the POS"):
        """Delete Bill on an order = cancel the order (the kitchen gets a
        CANCEL ticket for what it has). → True when handled here."""
        if not self.order:
            return False
        o = self.order
        if ask and not messagebox.askyesno(
                "Cancel order", "Cancel order %s?\n\nItems already sent to the kitchen get a CANCEL "
                "ticket. Nothing is sold." % R.summary(o, short=True), parent=self.pos.win):
            return True
        try:
            ids = R.cancel(self.order_id(), reason)
        except R.OrderClosed as e:
            messagebox.showwarning("Order", str(e), parent=self.pos.win)
            self.detach(clear=False)
            return True
        self.print_kots(ids)
        self.detach()
        self._notify()
        self.status("Order #%s cancelled%s." % (o.get("order_no"),
                                                 " — the kitchen got a CANCEL ticket" if ids else ""))
        return True

    # ── payment ──────────────────────────────────────────────
    def on_paid(self, invoice_id, lines):
        """Inside the bill's transaction (ui/pos._write_invoice): close the
        order with this bill; items the kitchen does not have yet get a
        ticket. A paid order that another PC changed stops the payment."""
        self._paid = None
        pos = self.pos
        oid = self.order_id()
        if not oid:
            if pos._loaded_invoice_id or not R.flag("rest_counter_as_takeaway"):
                return                              # editing a saved bill / plain counter sale
            try:
                if R.order_of_invoice(invoice_id):
                    return
                oid = R.open_order(self.pending_type if self.pending_type != "Dine-in" else "Takeaway")
            except Exception as e:                  # never stops the sale
                print("[DayBill] restaurant order not made:", e)
                return
        else:
            row = db.fetchone("SELECT status, version FROM rest_orders WITH (UPDLOCK) WHERE order_id=?",
                              (int(oid),))
            if not row or row["status"] not in R.RUNNING:
                raise R.OrderClosed("Order #%s was already paid or cancelled on another computer."
                                    % (self.order or {}).get("order_no"))
            if int(row["version"] or 0) != int(self.version or 0):
                theirs = self.to_cart(R.order_lines(oid))
                if self._sig(theirs) != self.base_sig:
                    raise R.OrderChanged(row["version"])
        kot_ids = []
        try:
            with db.savepoint():
                kot_ids = R.send_to_kitchen(oid, self.items(lines))
                R.close(oid, invoice_id, lines, self._incl())
        except (R.OrderChanged, R.OrderClosed):
            raise
        except Exception as e:
            print("[DayBill] restaurant order not closed:", e)
            kot_ids = []
        self._paid = (oid, kot_ids)

    def after_paid(self, invoice_id):
        """After the bill is saved: print the kitchen tickets, free the screen."""
        paid, self._paid = self._paid, None
        if not paid:
            return
        _oid, kot_ids = paid
        self.print_kots(kot_ids)
        self.detach(clear=False)
        self._notify()
