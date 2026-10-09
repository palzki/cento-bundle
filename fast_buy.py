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
        char_name: <character display name>  # e.g. "Mari"; "" for no-char items
    }
    Response JSON: { "success": bool, "code": int, "messages": [html, ...] }

    buy_id values for the daily items (verified live, nothing purchased):
        World Dungeon Key (x3) ......... 978   (needs char_name)
        Daily Quest Voucher ............ 578   (needs char_name)
        Abyssal Key (x3) ............... 321   (no character)
        [Centoria Tower] Proof of Blood  326   (no character)
    (Bundle Shop lives on /bundle-shop -- different endpoint -- still via UI flow.)
"""

import json
import re
import time

BUY_URL = "https://seal-centoria.com/webshop/api/buyItem"
SHOP_REFERER = "https://seal-centoria.com/webshop"

# Small politeness gap between consecutive POSTs so we don't hammer the server.
DELAY_BETWEEN_BUYS = 1.0  # seconds

# want_* flag  ->  (buy_id, needs_character, human label)
ITEM_MAP = {
    "want_dungeon_key":    ("978", True,  "World Dungeon Key (x3)"),
    "want_quest_voucher":  ("578", True,  "Daily Quest Voucher"),
    "want_abyssal_key":    ("321", False, "Abyssal Key (x3)"),
    "want_proof_of_blood": ("326", False, "Proof of Blood"),
}


def _clean(msg):
    """Strip the HTML tags the API wraps its messages in, collapse whitespace."""
    if isinstance(msg, (list, tuple)):
        msg = " ".join(str(m) for m in msg)
    text = re.sub(r"<[^>]+>", "", str(msg))
    return " ".join(text.split()).strip()


def _report(line, notify):
    """Print to console and, if a notifier was given (e.g. send_to_discord), send it too."""
    print(line)
    if notify:
        try:
            notify(line)
        except Exception as e:
            print(f"  [notify error] {e}")


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
                 times=1, flow_label=None, notify=None):
    """Fire one webshop purchase as a direct POST, reusing the logged-in context.

    notify: optional callable (e.g. send_to_discord) that receives each result
            line, so the fast path reports to Discord exactly like the old UI flow.
    """
    label = flow_label or f"buy_id {buy_id}"

    if "webshop" not in (page.url or ""):
        page.goto(SHOP_REFERER, wait_until="domcontentloaded")

    token = get_csrf_token(page)
    if not token:
        _report(f"  ⚠️  [{label}]: no csrf-token meta -- logged in / on the shop page?", notify)
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
        if i > 0:
            time.sleep(DELAY_BETWEEN_BUYS)
        resp = page.request.post(BUY_URL, form=form, headers=headers)
        status, text = resp.status, resp.text()

        # Parse the API's JSON {success, code, messages}; fall back to raw text.
        success, msg = None, text[:300]
        try:
            data = json.loads(text)
            success = bool(data.get("success"))
            msg = _clean(data.get("messages", text))
        except Exception:
            msg = _clean(text)

        ok = (status == 200) and (success is not False)
        suffix = f" [{i+1}/{times}]" if int(times) > 1 else ""
        if ok:
            _report(f"  ✅ [{label}{suffix} SUCCESS]: {msg}", notify)
            ok_any = True
        else:
            _report(f"  ❌ [{label}{suffix} FAILED] ({status}): {msg}", notify)
            return ok_any  # stop looping on first failure (already claimed / out of currency / etc.)
    return ok_any


# =====================================================================
# DROP-IN REPLACEMENT for the per-account purchase block in main()
# =====================================================================
def run_fast_purchases(page, account, bank_pass, char_name, notify=None):
    """Fire all flagged webshop purchases for one account via the fast API path.

    Mirrors the want_* flags in accounts.json. Pass notify=send_to_discord so each
    result is reported to Discord just like the old UI flow did.

    NOTE: Bundle Shop (want_bundle_shop) and the daily-login / seasonal claims are
    NOT handled here -- keep the existing UI functions for those.
    """
    first = True
    for flag, (buy_id, needs_char, label) in ITEM_MAP.items():
        if not account.get(flag, False):
            continue
        if needs_char and not char_name:
            _report(f"  ⏩ [{label} SKIPPED]: needs a character but none set for this account.", notify)
            continue
        if not first:
            time.sleep(DELAY_BETWEEN_BUYS)
        first = False
        buy_item_api(page, buy_id=buy_id, bank_password=bank_pass,
                     char_name=char_name if needs_char else "",
                     flow_label=label, notify=notify)


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
# HOW TO WIRE IT INTO login_bot.py
# =====================================================================
#   at top:  from fast_buy import run_fast_purchases
#   in main(), after run_login(...):
#       run_fast_purchases(page, account, bank_pass, char_name, notify=send_to_discord)
