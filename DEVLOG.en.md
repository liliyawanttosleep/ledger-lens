# Development log

> 中文版：[DEVLOG.md](DEVLOG.md). The two files carry the same entries; update both with every change.

Newest entries first. Each entry covers: what was done, why, files touched, how it was verified, what is left.

---

## 2026-11-13 · Project folder moved to D:\LedgerLens, English log added (no code changes)

**What was done**
- The project folder moved from `C:\Users\Wentao\Desktop\银行流水分析助手` to `D:\LedgerLens`, following the owner's machine-wide standard (project folders live on D:, the desktop holds shortcuts only). The desktop shortcut `流水分析助手.lnk` now points at `D:\LedgerLens\dist\流水分析助手.exe`.
- Added this file, an English translation of `DEVLOG.md`. `AGENTS.md` now asks for both logs to be updated together, and gained a short English preface.

**Why**: the owner asked for all recent projects to be brought in line with the standard in `C:\Users\Wentao\.claude\CLAUDE.md`: folder on D:, GitHub kept current, bilingual development log.

**Verification**: in the new location `git status` is clean and in sync with `origin/main`, and `.venv\Scripts\python samples\test_parse.py` passes on the six samples.
**Not verified**: `build.bat` was not re-run from the new location.

**Left over**
- `.venv` was copied, not recreated. `.venv\Scripts\python.exe` works, but the launcher scripts in `.venv\Scripts` (`pip.exe` and the like) still embed the old path; use `python -m pip`, or recreate the venv.
- User data is unaffected: it lives in `%APPDATA%\LedgerAssistant`, not in the project folder.
- Everything else as in v1.3.0.

---

## 2026-11-13 · First Android APK built and published (no code changes)

**What was done**
- After the owner ran `gh auth refresh -s workflow`, `.github/workflows/android.yml` was pushed. The first Actions build passed (run 43458671541) and `LedgerLens-android.apk` (about 0.5 MB, debug-signed) is attached to the v1.3.0 release.
- The "Downloads" table in the release notes now lists both platforms as available; `README.md` no longer says "not built yet".

**How to push a commit that touches a workflow**: git on this machine uses Git Credential Manager, whose token lacks the `workflow` scope; the `gh` token has it. Use gh's credentials for that one push without changing global config:
`git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin main`
(Ordinary pushes work with either credential. The earlier cherry-pick workaround is no longer needed; local and remote `main` match.)

**How to get an APK from now on**: a push to `main` that changes `android/` or `app/web/mobile/`, a `v*` tag, or a manual run from the Actions page all build the APK and attach it to the latest release. When releasing, run `gh release create` first, then confirm the APK is attached (`gh release view <tag> --json assets`). If only desktop code changed, trigger it by hand: `gh workflow run android.yml`.

**Verification**: the APK from the release was unpacked and inspected. It contains `classes.dex` and `AndroidManifest.xml`; `assets/www/` holds `index.html`, `m.js`, `m.css`, `i18n.js`, `echarts.min.js`, `icon.png`; `m.js` is the current version with the currency switcher.
**Not verified**: it has never been installed on a phone or an emulator. QR pairing, the `ledgerlens://pair` deep link and offline caching are untested inside the app.

**Left over**
- The APK is debug-signed. The signing key is reused through the workflow cache; if the cache expires, a new build cannot update an installed older one and the app has to be reinstalled.
- Everything else as in v1.3.0.

---

## 2026-11-13 · Platforms labelled on the release page (no code changes)

**What was done**: the v1.3.0 release notes became a "Downloads" table that lists Windows (`LedgerLens-windows.exe`, available) and Android (`LedgerLens-android.apk`, not built yet) separately; the download table in `README.md` says the same.

**Why**: the owner asked whether the Android build had been uploaded. In fact the Android source (`android/`) was in the repository but no APK had ever been built, the release only held the exe, and the README read as if the APK could be downloaded.

**Left over (blocked at the time)**
- No APK yet. The `gh` token had the scopes `gist, read:org, repo` but not `workflow`, so the commit containing `.github/workflows/android.yml` could not be pushed (local `main` was one commit ahead). The machine has no JDK or Android SDK, so a local build was not possible either.
- To unblock: the owner runs `gh auth refresh -h github.com -s workflow` and confirms in the browser → `git push origin main` → Actions builds the APK and attaches it to the latest release → remove "not built yet" from the release notes and README. The Android project had never been compiled, so the first build might need fixes.
- For every future release: keep this "Downloads" table in the release notes.

---

## 2026-11-13 · v1.3.0 — general internal-transfer detection, multiple currencies, combined report

**What was done**

1. **Internal-transfer detection no longer depends on how one person's statements are worded** (`transfers.py`, `categorize.py`, `parsers.py`). Two tiers:
   - **Marked automatically (high confidence)**. On top of the existing keywords, owner name, bank/broker counterparties and cross-account pairing:
     - `own_account()`: the description says it is the user's other account (`transfer to savings`, `转入本人账户`), or names **the last digits of another of the user's cards** (`转账至尾号5678`, `payment to card ending 9999`). The digits come from the `card` field across the whole database; they only count with context such as "尾号 / ending / acct", and not when the line contains purchase / 消费.
     - `parsers.guess_owner()`: reads the account holder from the statement header (`户名：`, `姓名：`, `Account holder:` …). Parse results carry `owner`, and on import `transfers.add_owner()` records it as the user's own name.
     - More keywords: Huabei / Baitiao repayments, Yu'e Bao / Lingqiantong / Zhaozhaobao transfers in and out, fund subscriptions and redemptions, FX purchase and settlement, Venmo / Cash App cash-outs, `sweep`, `brokerage transfer`, and so on.
     - Cross-currency pairing (3c): one out and one in, different accounts, different currencies, at most 5 days apart, within 3% at the current rate, both sides worded as transfers, worth at least 100 USD.
   - **Suspected, waiting for the user**: `transfers.suggestions()` groups records by description signature and scores them on general signals: money moves both ways (+2), at least 3 occurrences (+1), seen in at least 3 months (+1), mostly round amounts (+1), contains part of the user's name (+2), names a bank or account digits (+1). Only groups scoring 3 or more are listed. **It only asks; it changes no data.**
     The decision is stored through `transfers.decide_route(sig, True/False/None)` in the setting `transfer_routes`: `self` → records with that signature, including future imports, are marked as internal transfers; `other` → never marked automatically and never asked again, and records previously auto-marked on that route and still unpaired are restored.
   - UI: a "to confirm" bar at the top of the overview opens a dialog listing each route (description, account, count, in/out, total, date range, reasons) with two buttons, "my own account" and "no, count it". The import and data page has an entry point as well.
2. **Multiple currencies** (new file `app/fx.py`)
   - Currency per transaction: a "currency" column in a table is read row by row (`fx.code_of`); in text and screenshots a currency written next to the amount (`HK$ 320.00`, `15000日元`, `4,500원`, `fx.amount_currency`) is stored in `t["cur"]`. A bare `$` or `¥` is ambiguous and follows the file-level guess.
   - `guess_currency` now decides by frequency: a single foreign-currency line (one overseas purchase on a USD statement) no longer turns the whole file into that currency.
   - Symbols for 30 currencies; the currency can be chosen or changed in the import preview and in the transaction editor (`store.update_transaction` accepts `currency`).
   - **Separate view** (default): switch currency at the top; when the month has other currencies, an "other currencies" bar shows their income and expenses and switches on click.
   - **Combined view**: with two or more currencies there is a "combined" view (pseudo-currency `ALL`). All transactions are converted at the current reference rate into a base currency (selectable, setting `base_currency`, default the currency with the most transactions) and analysed together; details also show the original amount. Excel export and phone sync support it.
   - Rates: a built-in table dated 2026-11-13 is the offline fallback. The first visit to the combined view fetches `open.er-api.com/v6/latest/USD` and caches it in the setting `fx_rates`; "update rates" does it on demand. The request has no parameters and sends no user data. The UI credits the source as the API terms require.
3. The phone UI gained a currency switcher (it used to show only the first currency), including "combined".
4. `--selftest-sync` gained an `fx` check that the packaged program can fetch rates.

**Why**: the owner asked for internal-transfer detection that works for any user (judging from screenshots, dates, amounts, how often money moves between fixed accounts), and for several currencies shown separately with an optional combined report in one currency at the current rate.

**Files**: `app/fx.py` (new) `app/transfers.py` `app/categorize.py` `app/parsers.py` `app/main.py` `app/analysis.py` `app/store.py` `app/sync_server.py` `app/web/app.js` `app/web/style.css` `app/web/mobile/m.js` `app/web/mobile/m.css` `app/web/mobile/i18n.js` `README.md` `AGENTS.md`

**Verification**
- A constructed general scenario (two Chinese banks, a USD account, a JPY purchase, temporary database): `转账至尾号5678` was marked before the other statement was imported and paired afterwards; the header name was learned and `跨行转账 <name>` was marked; a 20,000 CNY outflow paired across currencies with a 2,960 USD inflow; a monthly transfer to the same person (3 out, 1 in) appeared in the suspected list, and confirm / reverse / undo all behaved correctly.
- A multi-currency CSV (currency column with CNY / JPY / USD) and a text statement (one `HK$` line): per-transaction currency correct, the file-level currency not skewed by the single line.
- Combined-view amounts checked by hand; switching base currency and fetching rates online (it succeeded at the time) worked.
- Looked at in a browser: desktop overview (separate and combined), transaction list, the confirmation dialog in Chinese and English, where non-Chinese UIs showed Chinese only in user data; phone overview with the currency switcher and combined view.
- Nine real files end to end: monthly income and expense totals equal v1.2.0, everything still USD, suspected list empty. No regression in `samples/test_parse.py`.
- **Not verified**: real multi-currency statements and real screenshots with currencies (constructed data only); the new French / Spanish / Korean strings were written but not viewed page by page; the suspicion scoring never fired on real data.

**Left over**
- The combined view uses the **current** rate, not the rate on the transaction date, so converted values for past months move with the rate. Cross-currency pairing likewise: old transfers whose rate has moved more than 3% will not pair.
- Rates cannot be entered by hand; currencies outside the built-in table count 1:1 in the combined view (the UI says so).
- A bare `$` / `¥` cannot tell USD from CAD or CNY from JPY; it follows the file-level guess and can be changed in the import preview.
- Confirmation of suspected routes is desktop only; `samples/` has no multi-currency sample yet.
- Everything else as in v1.2.0 (Android APK, Excel headers, the missing "unpaired" hint, and so on).

---

## 2026-11-13 · v1.2.0 — internal transfers with memory: new statements are matched against earlier ones

**What was done**

1. **Direction of money is recorded**: transactions gained a `flow` column (`in` / `out`). Previously a record marked `transfer` lost its direction, so the other side, imported later, could not be recognised as "one out, one in". The parser's `_mk(..., sign)` writes it and `store.add_import` stores it. Migration backfills old databases from `kind`; old transfer records have no direction and `transfers.flow()` guesses it from the description (no constraint if it cannot).
2. **Pairing is stored**: a new `pair_id` column makes the two records point at each other. `transfers.with_pairs()` attaches `pair: {account, card, date}` for the UI.
3. **Pairing in `transfers.reclassify()` rewritten** (it runs over the whole database after every import, so import order does not matter):
   - Conditions: same currency and amount, different account (account + card), opposite direction, dates at most 5 days apart (was 4), nearest date wins.
   - 3a: one side is already an internal transfer → the other is either an internal transfer too (pair only) or in a vague category (`其他支出 / 其他收入 / 转账收入`) and worded as a transfer.
   - 3b: neither side is settled → both must be in a vague category and at least one worded as a transfer. Records with a definite category (dining, salary …) are never changed by pairing.
   - `names_elsewhere()`: the description names another bank (for example `ELECTRONIC DEPOSIT JPMorgan Chase`) and the other account is not that bank → no pair.
   - A locked (hand-edited) internal transfer can act as an anchor for finding the other side but is not changed itself. `已退货` (returned goods) never pairs.
   - Stale pairs are cleaned up first (other side deleted, or one side changed back to income/expense).
4. **Route memory**: a description signature `sig()` (first four words after stripping channel prefixes and digits; used only with at least three words) that has paired at least twice, or that the user confirmed by hand, marks later records with the same signature, transfer wording and a vague category as internal transfers even before the other statement is imported. Signatures the user changed back to income/expense are never applied. The memory is recomputed from the database each time and not stored separately (delete the imports and the memory goes with them).
5. **UI**: in the transaction list and the category drill-down, a paired internal transfer shows "↔ other account · card · date" under its description; the phone drill-down does too (sync data carries `pair`). The import-finished message adds "matched N transfers with existing statements". The help text on the import and data page gained a paragraph.
6. `transfers.LAST = {pairs, pending, remembered}` keeps the result of the last run; `commit_import` returns `paired` / `pending`.
7. Fixed `build.bat`: the working-tree file had LF line endings and a BOM, `^` continuations failed under cmd and the script would not run. Now CRLF without BOM (`.gitattributes` already had `*.bat eol=crlf`).

**Why**: the owner asked that "a newly uploaded statement is checked against earlier ones, internal transfers judged from amount, time and transfer details; the program has memory".

**Files**: `app/transfers.py` `app/store.py` `app/parsers.py` `app/main.py` `app/sync_server.py` `app/web/app.js` `app/web/style.css` `app/web/mobile/m.js` `app/web/mobile/i18n.js`

**Verification**
- A staged import script (temporary database): checking account first (its payment line has no keyword) → then the credit card's `PAYMENT THANK YOU` → the checking line became an internal transfer and paired; another bank's `DEPOSIT ACH` paired with the earlier outflow; a friend's Zelle of the same amount and a same-amount purchase already filed under dining were not mispaired; after the same route had paired twice, a third month with only one side imported was recognised (`remembered=1`), and a water bill with the same prefix was not marked.
- A database with the old schema (no `flow` / `pair_id`) pairs correctly after upgrade; two credit cards each with a same-amount `PAYMENT THANK YOU` do not pair with each other.
- Nine real files end to end: monthly income and expense totals exactly equal v1.1.0; 24 pairs found (BoA checking ↔ BoA credit card payments, BoA ↔ US Bank transfers). Before the bank-name check, 7 pairs were wrong (the money really went to a Chase savings account / a broker that was not imported); after it they no longer pair.
- No regression in `samples/test_parse.py`. Under the dev server the English transaction list shows the pairing annotation with no console errors.
- **Not verified**: the phone pairing annotation is code only, never viewed on a phone or in a browser; the packaged exe only ran the self-test.

**Left over**
- In the real data 104 internal transfers still have no other side (the Chase savings and broker statements were not imported) and the UI does not flag "unpaired".
- Route memory has not fired on real data yet (`remembered=0`); verified on constructed data only.
- When the user changes one side of a pair back to income/expense, the other side does not follow.
- The card label in the pairing annotation ("尾号1234") is not translated in non-Chinese UIs.
- Android APK, Excel headers, Zelle between friends: as in v1.1.0.

---

## 2026-11-13 · v1.1.0 — smarter detection, returns excluded from spending, five languages

**What was done**

1. **Returns and refunds no longer count as spending or income** (`transfers.py::_refunds`, `analysis.py`)
   - If the same account has the original purchase ("same amount, same merchant, within 120 days") → purchase and refund are both marked `transfer / 已退货` and excluded.
   - Refunds with no matching purchase, and cashback (cashback, statement credit, fee waived) → the new `kind=refund`, which reduces spending in its category and is not income.
   - Reimbursements and tax refunds remain income. Credits on a credit-card statement default to refunds.
2. **Stronger internal-transfer detection** (`transfers.py`)
   - Owner matching extended: `REAL TIME PAYMENT TO/FROM <owner>`; Zelle contact nicknames of the form "first name + bank" (such as `Alex Chase`).
   - New rule `is_bank_move`: electronic transfers whose counterparty is a bank or broker (`ELECTRONIC DEPOSIT JPMorgan Chase`, `WEB AUTHORIZED PMT FID BKG SVC`) count as moves between the user's own accounts.
   - The overview gained an "excluded from totals" bar: counts and amounts of internal transfers / returned goods / refunds, each clickable for a line-by-line check.
3. **Salary detection** (`transfers.py::_propagate`): when a payer already has a definite category in another account (say a `SALARY` line at BoA), that payer's "other / transfer income" lines in other accounts get the same category. `ELECTRONIC DEPOSIT <employer>` at US Bank is therefore recognised as salary. The income card on the overview shows "of which salary".
4. **Five languages**: Chinese, English, French, Spanish, Korean. Switch at the bottom of the desktop sidebar, or on the phone's "sync" page.
   - UI: `web/mobile/i18n.js` (replacement after render); backend advice and health score: `app/i18n.py`.
   - `analysis.analyze(..., lang)`; `/api/sync?lang=`; setting `lang`.
5. **Other**: `.qbo` supported; importing the CSV and the QBO of the same statement is caught by fuzzy de-duplication (same account, same day, same amount, same start of description); the last four card digits in a file name are recognised more loosely (`Checking - 4563_...`); noise such as `Download from usbank.com` is removed.
6. `AGENTS.md` and this log were created.

**Why**: the owner tested with real BoA / Chase / US Bank statements. Transfers between their own accounts, transfers into a brokerage account, and returns and refunds were all counted as income and spending, and salary was filed as "transfer income" at some banks.

**Files**: `app/transfers.py` `app/analysis.py` (rewritten) `app/i18n.py` (new) `app/web/mobile/i18n.js` (new) `app/main.py` `app/parsers.py` `app/categorize.py` `app/sync_server.py` `app/store.py` `app/web/app.js` `app/web/index.html` `app/web/style.css` `app/web/mobile/m.js` `app/web/mobile/index.html`

**Verification**
- Nine real files from three banks imported end to end into a temporary database: income is down to salary, interest, a friend's Zelle and one airline payment; spending no longer contains self-transfers. With CSV and QBO imported together, all 83 QBO lines were flagged as duplicates.
- No regression on the six samples in `samples/test_parse.py`.
- Under the dev server every page of the English UI was scanned for leftover Chinese: only user data remained. Korean (phone sync page) and French (import dialog) spot-checked fine.
- **Not verified**: the Spanish UI was not viewed page by page; multilingual display on a real phone; the translations were written directly by the developer agent with no native-speaker review.

**Left over**
- Android APK still not built: pushing `.github/workflows/android.yml` needs the `workflow` scope, pending the owner running `gh auth refresh -h github.com -s workflow`. That commit is one ahead on local `main`. The Android project has never been compiled.
- Cross-account pairing (rule 3b) has not fired on its own on real data.
- A Zelle credit from a friend currently counts as "transfer income"; whether it is a split bill or a repayment is for the user to change by hand.
- Excel export headers are still Chinese.

---

## 2026-11-12 · v1.0.2 — internal-transfer detection

- New `app/transfers.py`: keywords + the user's own name (learned from `INDN:<name>`, editable under "import and data") + cross-account pairing. Runs after each import and at startup.
- Both sides of a credit-card payment (`PAYMENT FROM CHK` / `Mobile Banking payment to CRD`), `Ext Trnsfr`, `ACH transfer to <owner>` and Zelle to oneself are marked as internal transfers.
- Credit-card statement detection: wording for "payment received" marks the file as a credit card; the account name is inferred from the file name or its folder (`boa` → Bank of America); the last four card digits come from the file name.
- Transactions whose type was changed by hand are locked (`locked`).
- Verification: five BoA files and two Chase PDFs, all 78 internal transfers recognised; a friend's Zelle, salary and rent unaffected.

## 2026-11-12 · v1.0.1 — Chase credit-card statement fix

- Problem: on the first page a line of "calendar numbers + due date + points note" was read as a 3.50 USD transaction dated in the future; the singular heading `PURCHASE` was not recognised, so purchases were marked as income.
- Fix (`parsers.py`): points / interest-rate / calendar note lines are skipped whole; an amount followed by `Pts` / `points` is not money; singular `PURCHASE`, fees, interest and cash advances sections are recognised; transactions dated after today are dropped; merchant phone numbers are removed from descriptions.
- Verification: two real Chase statements parse as 8 purchases + 3 payments and 5 purchases + 5 payments, matching the statements.

## 2026-11-12 · v1.0.0 — first version

- Parsing: PDF (text / tables / scanned via OCR), screenshots (RapidOCR, offline), CSV, Excel, Word, HTML, OFX; income documents (payslips) handled separately.
- Analysis: KPIs, category donut, 12-month trend, month-over-month and 3-month average, daily and weekday distribution, merchants and accounts, health score, advice, suggested budget, recurring charges.
- UI: pywebview + ECharts, light and dark; editable preview before import, duplicate detection, category learning.
- Category drill-down: click a category / merchant / account to see each transaction's date, merchant, bank and card; the card comes from a "payment method" column or the last four digits.
- Phone sync: LAN service (off by default, 8-digit pairing code, lockout on wrong codes), phone web UI, Android WebView shell project.
- Packaging: PyInstaller single-file exe (about 130 MB); the icon is "a donut chart inside a water drop".
- Published on GitHub (public), commits use a noreply address, all samples are fictional data.
