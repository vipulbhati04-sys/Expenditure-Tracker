import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import os
from datetime import datetime, date
from collections import defaultdict

# ── Database setup ────────────────────────────────────────────────────────────

DB_FILE = "expenditure.db"

CATEGORIES = [
    "Food", "Transport", "Rent", "Utilities",
    "Entertainment", "Health", "Shopping", "Education", "Other"
]

FIXED_CATS = {"Rent", "Utilities"}

CAT_COLORS = {
    "Food": "#1D9E75", "Transport": "#378ADD", "Rent": "#D85A30",
    "Utilities": "#BA7517", "Entertainment": "#D4537E", "Health": "#534AB7",
    "Shopping": "#639922", "Education": "#0F6E56", "Other": "#888780",
}


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                amount      REAL    NOT NULL,
                description TEXT    DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                year_month  TEXT PRIMARY KEY,
                amount      REAL NOT NULL
            )
        """)


# ── Data helpers ──────────────────────────────────────────────────────────────

def add_expense(date_str, category, amount, description=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO expenses (date, category, amount, description) VALUES (?,?,?,?)",
            (date_str, category, amount, description)
        )


def delete_expense(expense_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))


def get_expenses(year, month):
    ym = f"{year}-{month:02d}"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE date LIKE ? ORDER BY date DESC",
            (f"{ym}-%",)
        ).fetchall()
    return rows


def get_all_expenses():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()


def set_budget(year, month, amount):
    ym = f"{year}-{month:02d}"
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO budgets (year_month, amount) VALUES (?,?)",
            (ym, amount)
        )


def get_budget(year, month):
    ym = f"{year}-{month:02d}"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT amount FROM budgets WHERE year_month=?", (ym,)
        ).fetchone()
    return row["amount"] if row else None


# ── Main Application ──────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Expenditure Tracker")
        self.geometry("900x650")
        self.minsize(700, 500)
        self.configure(bg="#f5f4f0")

        now = date.today()
        self.view_year  = tk.IntVar(value=now.year)
        self.view_month = tk.IntVar(value=now.month)

        init_db()
        self._build_ui()
        self.refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_metrics()
        self._build_notebook()

    def _build_header(self):
        hdr = tk.Frame(self, bg="#f5f4f0")
        hdr.pack(fill="x", padx=20, pady=(16, 4))

        tk.Label(hdr, text="Expenditure Tracker", font=("Georgia", 22),
                 bg="#f5f4f0", fg="#1a1917").pack(side="left")

        nav = tk.Frame(hdr, bg="#ffffff", relief="solid", bd=1)
        nav.pack(side="right", padx=4)

        tk.Button(nav, text="◀", command=self._prev_month,
                  bg="#ffffff", relief="flat", cursor="hand2",
                  font=("Arial", 11)).pack(side="left", padx=4, pady=4)

        self.month_label = tk.Label(nav, text="", font=("Georgia", 12, "italic"),
                                    bg="#ffffff", width=16)
        self.month_label.pack(side="left")

        tk.Button(nav, text="▶", command=self._next_month,
                  bg="#ffffff", relief="flat", cursor="hand2",
                  font=("Arial", 11)).pack(side="left", padx=4, pady=4)

    def _build_metrics(self):
        self.metrics_frame = tk.Frame(self, bg="#f5f4f0")
        self.metrics_frame.pack(fill="x", padx=20, pady=8)

    def _build_notebook(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#f5f4f0", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Arial", 11), padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", "#ffffff"), ("!selected", "#e8e6e1")],
                  foreground=[("selected", "#1a1917"), ("!selected", "#6b6963")])

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.nb.bind("<<NotebookTabChanged>>", lambda _: self.refresh())

        self.tab_add     = tk.Frame(self.nb, bg="#f5f4f0")
        self.tab_summary = tk.Frame(self.nb, bg="#f5f4f0")
        self.tab_entries = tk.Frame(self.nb, bg="#f5f4f0")
        self.tab_budget  = tk.Frame(self.nb, bg="#f5f4f0")

        self.nb.add(self.tab_add,     text="  Add Entry  ")
        self.nb.add(self.tab_summary, text="  Summary  ")
        self.nb.add(self.tab_entries, text="  All Entries  ")
        self.nb.add(self.tab_budget,  text="  Budget  ")

        self._build_add_tab()
        self._build_summary_tab()
        self._build_entries_tab()
        self._build_budget_tab()

    # ── Add Entry tab ─────────────────────────────────────────────────────────

    def _build_add_tab(self):
        p = self.tab_add
        card = self._card(p, "Log an Expense")
        card.pack(fill="x", padx=8, pady=8)

        grid = tk.Frame(card, bg="#ffffff")
        grid.pack(fill="x", padx=4, pady=4)
        grid.columnconfigure((0, 1), weight=1)

        # Date
        self._lbl(grid, "Date", 0, 0)
        self.inp_date = ttk.Entry(grid, font=("Arial", 12))
        self.inp_date.grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        self.inp_date.insert(0, date.today().isoformat())

        # Amount
        self._lbl(grid, "Amount (₹)", 0, 1)
        self.inp_amount = ttk.Entry(grid, font=("Arial", 12))
        self.inp_amount.grid(row=1, column=1, padx=6, pady=4, sticky="ew")

        # Category
        self._lbl(grid, "Category", 2, 0)
        self.inp_cat = ttk.Combobox(grid, values=CATEGORIES,
                                    state="readonly", font=("Arial", 12))
        self.inp_cat.current(0)
        self.inp_cat.grid(row=3, column=0, padx=6, pady=4, sticky="ew")

        # Description
        self._lbl(grid, "Description (optional)", 2, 1)
        self.inp_desc = ttk.Entry(grid, font=("Arial", 12))
        self.inp_desc.grid(row=3, column=1, padx=6, pady=4, sticky="ew")

        # Message label
        self.add_msg = tk.Label(card, text="", font=("Arial", 10),
                                bg="#ffffff", fg="#A32D2D")
        self.add_msg.pack(pady=(4, 0))

        # Add button
        tk.Button(card, text="Add Expense", command=self._add_expense,
                  bg="#1a1917", fg="#f5f4f0", font=("Arial", 12, "bold"),
                  relief="flat", cursor="hand2", pady=8
                  ).pack(fill="x", padx=6, pady=(6, 10))

        # Export card
        exp_card = self._card(p, "Export")
        exp_card.pack(fill="x", padx=8, pady=4)
        btn_row = tk.Frame(exp_card, bg="#ffffff")
        btn_row.pack(fill="x", padx=4, pady=6)

        self._sec_btn(btn_row, "Export This Month (CSV)",
                      self._export_month).pack(side="left", padx=6)
        self._sec_btn(btn_row, "Export All Data (CSV)",
                      self._export_all).pack(side="left", padx=6)

    def _add_expense(self):
        date_str = self.inp_date.get().strip()
        amt_str  = self.inp_amount.get().strip()
        cat      = self.inp_cat.get()
        desc     = self.inp_desc.get().strip()

        # Validate date
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self._set_msg(self.add_msg, "Invalid date. Use YYYY-MM-DD.", "error")
            return

        # Validate amount
        try:
            amount = float(amt_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            self._set_msg(self.add_msg, "Enter a valid positive amount.", "error")
            return

        add_expense(date_str, cat, amount, desc)
        self.inp_amount.delete(0, "end")
        self.inp_desc.delete(0, "end")
        self._set_msg(self.add_msg, f"✓ Added ₹{amount:,.2f} under {cat}", "ok")
        self.refresh()

    # ── Summary tab ───────────────────────────────────────────────────────────

    def _build_summary_tab(self):
        p = self.tab_summary

        # Category breakdown card
        cat_card = self._card(p, "Category Breakdown")
        cat_card.pack(fill="both", expand=True, padx=8, pady=8)

        self.cat_frame = tk.Frame(cat_card, bg="#ffffff")
        self.cat_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # Daily totals card
        day_card = self._card(p, "Top Spending Days")
        day_card.pack(fill="x", padx=8, pady=(0, 8))

        self.day_frame = tk.Frame(day_card, bg="#ffffff")
        self.day_frame.pack(fill="x", padx=4, pady=4)

    def _render_summary(self):
        y, m = self.view_year.get(), self.view_month.get()
        rows = get_expenses(y, m)

        # Clear
        for w in self.cat_frame.winfo_children():
            w.destroy()
        for w in self.day_frame.winfo_children():
            w.destroy()

        if not rows:
            tk.Label(self.cat_frame, text="No expenses this month.",
                     font=("Georgia", 12, "italic"), bg="#ffffff",
                     fg="#9c9890").pack(pady=20)
            return

        total = sum(r["amount"] for r in rows)
        by_cat = defaultdict(float)
        by_day = defaultdict(float)
        for r in rows:
            by_cat[r["category"]] += r["amount"]
            by_day[r["date"]] += r["amount"]

        # Category bars
        sorted_cats = sorted(by_cat, key=by_cat.get, reverse=True)
        max_amt = by_cat[sorted_cats[0]] if sorted_cats else 1

        for cat in sorted_cats:
            amt  = by_cat[cat]
            pct  = amt / total * 100
            col  = CAT_COLORS.get(cat, "#888")
            row  = tk.Frame(self.cat_frame, bg="#ffffff")
            row.pack(fill="x", pady=3, padx=4)

            tk.Label(row, text=cat, width=14, anchor="w",
                     font=("Arial", 11), bg="#ffffff").pack(side="left")

            bar_bg = tk.Frame(row, bg="#e8e6e1", height=10, width=300)
            bar_bg.pack(side="left", padx=6)
            bar_bg.pack_propagate(False)

            fill_w = int(300 * amt / max_amt)
            tk.Frame(bar_bg, bg=col, height=10, width=fill_w).place(x=0, y=0)

            tk.Label(row, text=f"₹{amt:,.2f}  ({pct:.1f}%)",
                     font=("Arial", 10), bg="#ffffff",
                     fg="#6b6963").pack(side="left")

        # Top 5 days
        top_days = sorted(by_day.items(), key=lambda x: x[1], reverse=True)[:5]
        for d, amt in top_days:
            r = tk.Frame(self.day_frame, bg="#ffffff")
            r.pack(fill="x", pady=2, padx=4)
            tk.Label(r, text=d, font=("Arial", 11), bg="#ffffff",
                     width=14, anchor="w").pack(side="left")
            tk.Label(r, text=f"₹{amt:,.2f}", font=("Arial", 11, "bold"),
                     bg="#ffffff", fg="#1a1917").pack(side="left")

    # ── All Entries tab ───────────────────────────────────────────────────────

    def _build_entries_tab(self):
        p = self.tab_entries

        # Filter row
        frow = tk.Frame(p, bg="#f5f4f0")
        frow.pack(fill="x", padx=8, pady=8)

        tk.Label(frow, text="Category:", bg="#f5f4f0",
                 font=("Arial", 11)).pack(side="left")
        self.filter_cat = ttk.Combobox(frow, values=["All"] + CATEGORIES,
                                       state="readonly", width=14,
                                       font=("Arial", 11))
        self.filter_cat.current(0)
        self.filter_cat.pack(side="left", padx=6)
        self.filter_cat.bind("<<ComboboxSelected>>", lambda _: self._render_entries())

        tk.Label(frow, text="Search:", bg="#f5f4f0",
                 font=("Arial", 11)).pack(side="left", padx=(10, 0))
        self.filter_search = ttk.Entry(frow, font=("Arial", 11), width=20)
        self.filter_search.pack(side="left", padx=6)
        self.filter_search.bind("<KeyRelease>", lambda _: self._render_entries())

        # Treeview
        cols = ("date", "category", "amount", "description")
        self.tree = ttk.Treeview(p, columns=cols, show="headings",
                                 selectmode="browse")
        self.tree.heading("date",        text="Date")
        self.tree.heading("category",    text="Category")
        self.tree.heading("amount",      text="Amount (₹)")
        self.tree.heading("description", text="Description")
        self.tree.column("date",        width=110, anchor="center")
        self.tree.column("category",    width=130, anchor="center")
        self.tree.column("amount",      width=120, anchor="e")
        self.tree.column("description", width=300)

        vsb = ttk.Scrollbar(p, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        vsb.pack(side="left", fill="y", pady=(0, 8))

        # Delete button
        tk.Button(p, text="Delete Selected", command=self._delete_selected,
                  bg="#A32D2D", fg="white", font=("Arial", 11),
                  relief="flat", cursor="hand2", pady=6
                  ).pack(fill="x", padx=8, pady=(0, 8))

        # Store row id → expense id mapping
        self._tree_ids = {}

    def _render_entries(self):
        y, m = self.view_year.get(), self.view_month.get()
        rows = get_expenses(y, m)

        cat_f  = self.filter_cat.get()
        search = self.filter_search.get().lower().strip()

        filtered = [
            r for r in rows
            if (cat_f == "All" or r["category"] == cat_f)
            and (not search or search in (r["description"] or "").lower())
        ]

        self.tree.delete(*self.tree.get_children())
        self._tree_ids.clear()

        for r in filtered:
            iid = self.tree.insert("", "end", values=(
                r["date"], r["category"],
                f"₹{r['amount']:,.2f}",
                r["description"] or "—"
            ))
            self._tree_ids[iid] = r["id"]

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a row to delete.")
            return
        if messagebox.askyesno("Confirm", "Delete selected expense?"):
            delete_expense(self._tree_ids[sel[0]])
            self.refresh()

    # ── Budget tab ────────────────────────────────────────────────────────────

    def _build_budget_tab(self):
        p = self.tab_budget

        bcard = self._card(p, "Monthly Budget Limit")
        bcard.pack(fill="x", padx=8, pady=8)

        row = tk.Frame(bcard, bg="#ffffff")
        row.pack(fill="x", padx=6, pady=6)

        tk.Label(row, text="₹", font=("Arial", 14), bg="#ffffff").pack(side="left")
        self.budget_inp = ttk.Entry(row, font=("Arial", 13), width=16)
        self.budget_inp.pack(side="left", padx=6)
        self._sec_btn(row, "Set Budget", self._set_budget).pack(side="left")

        self.budget_info = tk.Label(bcard, text="", font=("Arial", 11),
                                    bg="#ffffff", justify="left")
        self.budget_info.pack(anchor="w", padx=8, pady=(4, 8))

        # Progress canvas
        self.budget_canvas = tk.Canvas(bcard, bg="#ffffff", height=24,
                                       highlightthickness=0)
        self.budget_canvas.pack(fill="x", padx=8, pady=(0, 10))

        # Fixed vs Variable
        fv_card = self._card(p, "Fixed vs Variable Expenses")
        fv_card.pack(fill="x", padx=8, pady=(0, 8))
        self.fv_frame = tk.Frame(fv_card, bg="#ffffff")
        self.fv_frame.pack(fill="x", padx=6, pady=6)

    def _set_budget(self):
        try:
            val = float(self.budget_inp.get())
            if val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Enter a valid positive budget amount.")
            return
        set_budget(self.view_year.get(), self.view_month.get(), val)
        self.refresh()

    def _render_budget(self):
        y, m = self.view_year.get(), self.view_month.get()
        budget = get_budget(y, m)
        rows   = get_expenses(y, m)
        total  = sum(r["amount"] for r in rows)

        if budget is not None:
            self.budget_inp.delete(0, "end")
            self.budget_inp.insert(0, str(int(budget)))

        if budget and budget > 0:
            pct  = min(total / budget, 1.0)
            rem  = budget - total
            col  = "#639922" if pct < 0.8 else ("#EF9F27" if pct < 1.0 else "#E24B4A")
            status = "✓ On track" if pct < 0.8 else ("⚠ Nearing limit" if pct < 1.0 else "✗ Budget exceeded")
            self.budget_info.config(
                text=f"Spent: ₹{total:,.2f}  /  Budget: ₹{budget:,.2f}\n"
                     f"{'Remaining' if rem >= 0 else 'Over by'}: ₹{abs(rem):,.2f}   {status}",
                fg=col
            )
            # Draw progress bar
            self.budget_canvas.update_idletasks()
            w = self.budget_canvas.winfo_width() or 400
            self.budget_canvas.delete("all")
            self.budget_canvas.create_rectangle(0, 4, w, 20, fill="#e8e6e1", outline="")
            self.budget_canvas.create_rectangle(0, 4, int(w * pct), 20, fill=col, outline="")
        else:
            self.budget_info.config(text="No budget set for this month.", fg="#9c9890")
            self.budget_canvas.delete("all")

        # Fixed vs Variable
        for w in self.fv_frame.winfo_children():
            w.destroy()

        fixed = sum(r["amount"] for r in rows if r["category"] in FIXED_CATS)
        variable = total - fixed

        for label, amt, col in [("Fixed", fixed, "#D85A30"), ("Variable", variable, "#378ADD")]:
            col_f = tk.Frame(self.fv_frame, bg="#f0ede8", padx=12, pady=10)
            col_f.pack(side="left", expand=True, fill="x", padx=6)
            tk.Label(col_f, text=label, font=("Arial", 10),
                     bg="#f0ede8", fg="#6b6963").pack()
            tk.Label(col_f, text=f"₹{amt:,.2f}", font=("Arial", 14, "bold"),
                     bg="#f0ede8", fg=col).pack()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_month(self):
        rows = get_expenses(self.view_year.get(), self.view_month.get())
        self._write_csv(rows, f"expenses_{self.view_year.get()}_{self.view_month.get():02d}.csv")

    def _export_all(self):
        self._write_csv(get_all_expenses(), "expenses_all.csv")

    def _write_csv(self, rows, default_name):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=default_name
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Category", "Amount", "Description"])
            for r in rows:
                writer.writerow([r["id"], r["date"], r["category"],
                                  r["amount"], r["description"]])
        messagebox.showinfo("Exported", f"Saved to:\n{path}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _prev_month(self):
        m, y = self.view_month.get(), self.view_year.get()
        if m == 1:
            self.view_month.set(12); self.view_year.set(y - 1)
        else:
            self.view_month.set(m - 1)
        self.refresh()

    def _next_month(self):
        m, y = self.view_month.get(), self.view_year.get()
        if m == 12:
            self.view_month.set(1); self.view_year.set(y + 1)
        else:
            self.view_month.set(m + 1)
        self.refresh()

    # ── Metrics bar ───────────────────────────────────────────────────────────

    def _render_metrics(self):
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        y, m = self.view_year.get(), self.view_month.get()
        rows   = get_expenses(y, m)
        total  = sum(r["amount"] for r in rows)
        budget = get_budget(y, m)

        today_d = date.today()
        is_cur  = (y == today_d.year and m == today_d.month)
        days    = today_d.day if is_cur else (date(y, m % 12 + 1, 1) - date(y, m, 1)).days if m < 12 else 31
        avg     = total / days if days else 0

        metrics = [
            ("Total Spent",    f"₹{total:,.2f}", "#1a1917"),
            ("Entries",        str(len(rows)),   "#1a1917"),
            ("Daily Average",  f"₹{avg:,.2f}",   "#1a1917"),
        ]
        if budget:
            rem = budget - total
            col = "#3B6D11" if rem > 0 else "#A32D2D"
            metrics.append(("Budget Left", f"₹{rem:,.2f}", col))

        for label, value, col in metrics:
            card = tk.Frame(self.metrics_frame, bg="#ffffff",
                            relief="solid", bd=1, padx=14, pady=10)
            card.pack(side="left", padx=6, pady=2)
            tk.Label(card, text=label, font=("Arial", 9),
                     bg="#ffffff", fg="#6b6963").pack(anchor="w")
            tk.Label(card, text=value, font=("Georgia", 16),
                     bg="#ffffff", fg=col).pack(anchor="w")

    # ── Master refresh ────────────────────────────────────────────────────────

    def refresh(self):
        y, m = self.view_year.get(), self.view_month.get()
        mn = date(y, m, 1).strftime("%B %Y")
        self.month_label.config(text=mn)
        self._render_metrics()

        tab = self.nb.index(self.nb.select())
        if tab == 0:
            pass  # Add tab is static
        elif tab == 1:
            self._render_summary()
        elif tab == 2:
            self._render_entries()
        elif tab == 3:
            self._render_budget()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _card(self, parent, title):
        outer = tk.Frame(parent, bg="#ffffff", relief="solid", bd=1)
        tk.Label(outer, text=title.upper(), font=("Arial", 9),
                 bg="#ffffff", fg="#6b6963",
                 letterSpacing=2).pack(anchor="w", padx=12, pady=(10, 4))
        return outer

    def _lbl(self, parent, text, row, col):
        tk.Label(parent, text=text.upper(), font=("Arial", 8),
                 bg="#ffffff", fg="#6b6963").grid(
            row=row, column=col, sticky="w", padx=6, pady=(8, 0))

    def _sec_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg="#f0ede8", fg="#1a1917", font=("Arial", 10),
                         relief="flat", cursor="hand2", padx=10, pady=6)

    def _set_msg(self, label, text, kind):
        label.config(text=text, fg="#3B6D11" if kind == "ok" else "#A32D2D")
        self.after(3000, lambda: label.config(text=""))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
