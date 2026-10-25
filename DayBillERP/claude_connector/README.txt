DayBill ERP - Claude connector (read-only reports)
====================================================

What it does
  Lets Claude (the Claude desktop app, including Cowork) read your DayBill
  database and answer questions such as:
    - "Sales this month by day"          - "VAT return for Q3 2026"
    - "Top 10 products and their profit"  - "Which items are low on stock?"
    - "Who owes me money? Show aging"     - "Day close for today"
    - "Statement for customer Ali"        - "Profit and loss for September"
    - "What should I order this week?"    - "Which batches will expire unsold?"
    - "What do people buy with milk?"     - "Which supplier is cheapest for rice?"
  It can NEVER change, add or delete anything (read-only, see Safety).

Install (on the PC where DayBill + SQL Server work)
  1. Keep this "claude_connector" folder inside the DayBill folder
     (it uses DayBill's config\ and modules\ folders).
  2. Install the Claude desktop app (claude.ai/download) and sign in once.
  3. Double-click INSTALL_CLAUDE_CONNECTOR.bat
       - installs the "mcp" Python package
       - tests the DayBill database connection
       - adds "daybill" to Claude's config (a backup of the old config is kept)
  4. Fully QUIT Claude (tray icon near the clock > Quit) and open it again.
  5. Ask: "Using DayBill, show today's sales."

  The PC must be on, with the Claude app open, for the connector to answer.

Which database / company?
  The same one DayBill uses (config\db_config.json - the one chosen in
  Login > Database Settings). To point Claude at a different company or use
  the read-only login, rename connector_config.example.json to
  connector_config.json and fill it in.

Safety
  - Only SELECT queries; the connection is opened read-only and every
    transaction is rolled back.
  - run_sql refuses INSERT/UPDATE/DELETE/DROP/EXEC/INTO/... and multiple
    statements.
  - Extra lock (recommended): run create_readonly_login.sql in SSMS, then use
    that login in connector_config.json. SQL Server itself will then refuse
    any change.
  - Your business data is sent to Claude only when you ask a question that
    needs it.

Remove
  Double-click UNINSTALL_CLAUDE_CONNECTOR.bat, then restart Claude.

NEW in v6.3 - AI inventory management (same engine as DayBill ▸ Smart Insights)
  inventory_health   START HERE: stock health score 0-100 + what to do now
  stock_forecast     sells/day, trend, days of stock left, run-out date
  reorder_plan       what to order, quantity in the purchase unit, per supplier
  abc_analysis       A/B/C items by revenue / profit / qty, A items at risk
  expiry_alerts      batches near expiry, how much will NOT sell in time, advice
  branch_transfers   stock to move between branches instead of buying
  bought_together    items bought in the same bill (shelf / combo offers)
  supplier_prices    one product's price per supplier, cheapest, trend
  data_check         missing barcode / cost / price, minus stock, duplicates ...
  price_check        items below cost or with a thin margin
  sales_trends       this week vs last, busiest day / hour, faster / slower items
  daily_briefing     the owner's short briefing + things to check today

Ready-made prompts (in Claude: + ▸ DayBill ERP)
  Daily stock check · What to order this week · Weekly business review ·
  Expiry & dead stock clean-up · Price & margin check · Fix product data ·
  Month-end VAT check

Easy install from DayBill: Smart Insights ▸ 🔌 Claude desktop.

Tools Claude gets
  list_reports, run_report  -> every report of DayBill's Reports Center
    (trial balance, P&L, balance sheet, cash/bank/day book, VAT return,
    sales/POS/purchase registers, stock, stock movement, item ledger ...)
  database_info, business_overview, sales_report, top_products,
  slow_moving_products, vat_report, stock_report, product_lookup,
  customer_balances, supplier_balances, party_statement, purchase_report,
  expense_report, day_close, find_invoice, profit_and_loss, trial_balance,
  balance_sheet, account_ledger, run_sql, list_tables, describe_table
