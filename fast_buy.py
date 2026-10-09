"""
fast_buy.py  --  drop-in speed-up for login_bot.py
===================================================

WHY THIS EXISTS
    Your purchase_* functions drive the whole webshop UI (goto -> networkidle ->
    click #buy-item -> selectric dropdown -> fill -> Buy). That's ~4-5 full page
    waits per item. The site actually buys via a single POST to
    /webshop/api/buyItem.

    Because you're already running a LOGGED-IN Playwright context that has passed
    Cloudflare, `page.request` reuses that same context's cookies (laravel_session,
    XSRF-TOKEN, cf_clearance) and network stack. So we fire that POST directly:
        - no curl_cffi, no manual cookie pasting, no re-solving Cloudflare.
    Each buy drops from ~15s to well under 1s.

CONFIRMED FROM THE SITE ITSELF (webshop.6.2.2 JS + /api/viewItem + /api/itemList):
    POST https://seal-centoria.com/webshop/api/buyItem
    headers: X-CSRF-TOKEN: <meta name="csrf-token"> content, X-Requested-With: XMLHttpRequest
    data: {
        pw:        <bank password>,
        buy_id:    <item id>,                # == the item's `id` in /api/itemList
        payment:   "silver",                 # the only pay_method option ("Cent")
        char_name: <character display name>  # e.g. "Pozyomka"; "" for no-char items
    }

    buy_id values for your daily items (verified live, nothing purchased):
        World Dungeon Key (x3) ......... 978   (needs char_name)
        Daily Quest Voucher ............ 578   (needs char_name)
        Abyssal Key (x3) ............... 321   (no character)
        [Centoria Tower] Proof of Blood  326   (no character)
    (Bundle Shop lives on /bundle-shop -- different endpoint -- still via UI flow.)
"""

BUY_URL = "https://seal-centoria.com/webshop/api/buyItem"
SHOP_REFERER = "https://seal-centoria.com/webshop"

# want_* flag  ->  (buy_id, needs_character, human label)
ITEM_MAP = {
    "want_dungeon_key":    ("978", True,  "World Dungeon Key (x3)"),
    "want_quest_voucher":  ("578", True,  "Daily Quest Voucher"),
    "want_abyssal_key":    ("321", False, "Abyssal Key (x3)"),
    "want_proof_of_blood": ("326", False, "Proof of Blood"),
}


# =====================================================================
# CSRF token (read fresh each buy so it always matches the live session)
# =====================================================================
def get_csrf_token(page):
    return page.evaluate(
        "() => { const m = document.querySelector(\"meta[name='csrf-token']\");"
        " return m ? m.content : null; }"
    )


# =====================================================================
# THE FAST BUY
# =====================================================================
def buy_item_api(page, buy_id, bank_password, char_name="", payment="silver",
                 times=1, flow_label=None):
    """Fire one webshop purchase as a direct POST, reusing the logged-in context."""
    label = flow_label or f"buy_id {buy_id}"

    if "webshop" not in (page.url or ""):
        page.goto(SHOP_REFERER, wait_until="domcontentloaded")

    token = get_csrf_token(page)
    if not token:
        print(f"  [!] [{label}] No csrf-token meta -- logged in / on the shop page?")
        return False

    form = {"pw": bank_password, "buy_id": str(buy_id),
            "payment": payment, "char_name": char_name}
    headers = {
        "accept": "*/*",
        "x-csrf-token": token,
        "x-requested-with": "XMLHttpRequest",
        "referer": SHOP_REFERER,
        "origin": "https://seal-centoria.com",
    }

    ok_any = False
    for i in range(max(1, int(times))):
        resp = page.request.post(BUY_URL, form=form, headers=headers)
        status, text = resp.status, resp.text()
        low = text.lower().replace(" ", "")
        # API returns JSON {success: bool, messages: "..."}.
        ok = status == 200 and '"success":false' not in low
        bad = any(w in low for w in ("already", "invalid", "soldout",
                                     "insufficient", "notenough", "failed", "minimum"))
        if ok and not bad:
            print(f"  [OK]   [{label}] x{i+1} -> {status}: {text[:200]}")
            ok_any = True
        else:
            print(f"  [FAIL] [{label}] x{i+1} -> {status}: {text[:300]}")
            return ok_any  # stop on first failure (already claimed / out of currency / etc.)
    return ok_any


# =====================================================================
# DROP-IN REPLACEMENT for the per-account purchase block in main()
# =====================================================================
def run_fast_purchases(page, account, bank_pass, char_name):
    """Fire all flagged webshop purchases for one account via the fast API path.

    Mirrors the want_* flags you already use in accounts.json. Call it in main()
    right after run_login(...), in place of the individual purchase_* calls.
    Returns nothing; prints OK/FAIL per item.

    NOTE: Bundle Shop (want_bundle_shop) and the daily-login / seasonal claims are
    NOT handled here -- keep your existing UI functions for those.
    """
    for flag, (buy_id, needs_char, label) in ITEM_MAP.items():
        if not account.get(flag, False):
            continue
        if needs_char and not char_name:
            print(f"  [SKIP] [{label}] needs a character but none set for this account.")
            continue
        buy_item_api(page, buy_id=buy_id, bank_password=bank_pass,
                     char_name=char_name if needs_char else "",
                     flow_label=label)


# =====================================================================
# OPTIONAL: re-discover ids if the shop ever changes (reads only, buys nothing)
# =====================================================================
def harvest_buy_ids(page, name_filter=""):
    """Query /api/itemList and print id + name for items matching name_filter.
    Run from a logged-in session. Purely reads the catalog."""
    rows = page.evaluate("""async (needle) => {
        const token = document.querySelector("meta[name='csrf-token']").content;
        const body = new URLSearchParams({draw:'1', start:'0', length:'2000',
            'search[value]':'', 'order[0][column]':'0', 'order[0][dir]':'asc',
            'columns[0][data]':'0'});
        const r = await fetch('https://seal-centoria.com/webshop/api/itemList', {
            method:'POST',
            headers:{'X-CSRF-TOKEN':token,'X-Requested-With':'XMLHttpRequest',
                     'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
            body: body.toString()});
        const j = await r.json();
        const strip = s => (s||'').replace(/&#0?39;/g,"'").replace(/&amp;/g,'&').replace(/<[^>]+>/g,'').trim();
        return j.data.map(it => ({id: it.id, name: strip(it.name)}))
                     .filter(x => x.name.toLowerCase().includes((needle||'').toLowerCase()));
    }""", name_filter)
    print(f"\n===== itemList matches for '{name_filter}' ({len(rows)}) =====")
    for r in rows:
        print(f"  buy_id={r['id']:<6}  {r['name']}")
    print("=" * 50 + "\n")
    return rows


# =====================================================================
# HOW TO WIRE IT INTO login_bot.py  (minimal, keeps your UI code as fallback)
# =====================================================================
#   at top of login_bot.py:
#       from fast_buy import run_fast_purchases
#
#   in main(), inside the `for account in accounts_config:` try-block, replace the
#   five purchase_*() if-blocks with ONE line (keep bundle + daily/seasonal as-is):
#
#       run_login(page, username, account.get("password", ""))
#
#       run_fast_purchases(page, account, bank_pass, char_name)   # <-- fast webshop buys
#
#       if account.get("want_bundle_shop", False):
#           purchase_bundle_shop_item(page, bank_pass)            # still UI (different page)
#       if account.get("want_normal_daily", False):
#           claim_normal_daily_login(page, char_name)             # still UI (Turnstile)
#       if account.get("want_seasonal_claims", False):
#           claim_daily_login_events(page, char_name)             # still UI (Turnstile)
