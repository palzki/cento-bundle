import os
import time
import requests
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID", "")

def send_to_discord(message):
    """Dispatches real-time log payloads directly to Sensei's Discord channel if enabled globally."""
    # 1. Read the toggle from the environment file (defaults to "True" if missing)
    enable_discord = os.getenv("ENABLE_DISCORD", "True").strip().lower() == "true"
    
    # 2. Check if Discord features are globally turned off
    if not enable_discord:
        return

    # 3. Check if the webhook URL configuration is missing
    if not DISCORD_WEBHOOK_URL:
        print(message)  # Fallback to local console printout
        return

    # 4. Construct the payload data structure and send to Discord
    payload = {"content": message}
    if DISCORD_USER_ID:
        payload["content"] = f"{message}"

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code not in [200, 204]:
            print(f"[Discord Error] Failed with status code: {response.status_code}")
    except Exception as e:
        print(f"[Discord Exception] Failed to send network request: {e}")

# =====================================================================
# STEP 1: LOGIN FLOW
# =====================================================================
def run_login(page, username, password):
    page.goto("https://seal-centoria.com/")
    page.wait_for_load_state("domcontentloaded")
    
    page.locator("input[name='username']").first.fill(username)
    page.wait_for_timeout(500)
    page.locator("input[name='password']").first.fill(password)
    
    page.locator("button[type='submit'], button:has-text('Log in')").first.click()
    page.wait_for_load_state("networkidle")

    # Verify successful login gate before continuing
    manage_button = page.locator("legend:has-text('MEMBER PANEL')").first
    manage_button.wait_for(state="visible", timeout=10000)


# =====================================================================
# TRANSACTION TOAST MONITOR
# =====================================================================
def verify_transaction_status(page, character_name, flow_label):
    # Enforce the :visible filter on every selector path so Playwright skips hidden placeholders!
    notification = page.locator(".alert-success:visible, .alert-danger:visible, [data-notify='container']:visible").first
    try:
        # Now this wait command will lock strictly onto the active floating toast!
        notification.wait_for(state="visible", timeout=7000)
        
        message_text = notification.inner_text()
        element_classes = notification.get_attribute("class") or ""
        
        # clean_label = flow_label.lower().replace(" ", "_")
        # page.screenshot(path=f"purchase_{clean_label}_{character_name}_complete.png")

        if "alert-danger" in element_classes or "already claimed" in message_text.lower() or "invalid" in message_text.lower():
            print(f"  ❌ [{flow_label} FAILED]: {message_text}")
            send_to_discord(f"  ❌ [{flow_label} FAILED]: {message_text}")
            if "Captcha" in message_text or "captcha" in message_text:
                return "RETRY_CAPTCHA"
            return False
        else:
            print(f"  ✅ [{flow_label} SUCCESS]: {message_text}")
            send_to_discord(f"  ✅ [{flow_label} SUCCESS]: {message_text}")
            return True
            
    except Exception as raw_error:
        print(f"  ⚠️  [{flow_label}]: Timed out waiting for status toast response or text serialization.")
        print(f"  🔍 [DIAGNOSTIC ERROR ENGINE LOG]: {raw_error}")
        return False


# =====================================================================
# CHECKOUT FLOWS
# =====================================================================
def purchase_world_dungeon_key(page, bank_password, character_name):
    page.goto("https://seal-centoria.com/webshop?showItem=World%20Dungeon%20Key")
    page.wait_for_load_state("networkidle")
    page.locator("#buy-item").first.click()
    page.wait_for_load_state("networkidle")

    page.locator(".selectric .label:has-text('Select Character')").first.click()
    page.locator(f".selectric-scroll li:has-text('{character_name}')").first.click()
   
    page.locator("input[placeholder='Bank Password']").first.fill(bank_password)
    modal_buy_button = page.locator(".modal-content button:has-text('Buy'), .modal-footer button:has-text('Buy')").first
    modal_buy_button.click()

    verify_transaction_status(page, character_name, "World Dungeon Key")

def purchase_abyssal_key(page, bank_password, character_name):
    page.goto("https://seal-centoria.com/webshop?showItem=Abyssal%20Key%20x3")
    page.wait_for_load_state("networkidle")
    page.locator("#buy-item").first.click()
    page.wait_for_load_state("networkidle")
   
    page.locator("input[placeholder='Bank Password']").first.fill(bank_password)
    modal_buy_button = page.locator(".modal-content button:has-text('Buy'), .modal-footer button:has-text('Buy')").first
    # uncomment to actually buy
    # modal_buy_button.click()

    verify_transaction_status(page, character_name, "Abyssal Key")

def purchase_daily_quest_voucher(page, bank_password, character_name):
    page.goto("https://seal-centoria.com/webshop?showItem=Daily%20Quest%20Voucher")
    page.wait_for_load_state("networkidle")
    page.locator("#buy-item").first.click()
    page.wait_for_load_state("networkidle")

    page.locator(".selectric .label:has-text('Select Character')").first.click()
    page.locator(f".selectric-scroll li:has-text('{character_name}')").first.click()
   
    page.locator("input[placeholder='Bank Password']").first.fill(bank_password)
    modal_buy_button = page.locator(".modal-content button:has-text('Buy'), .modal-footer button:has-text('Buy')").first
    modal_buy_button.click()

    verify_transaction_status(page, character_name, "Daily Quest Voucher")


def purchase_proof_of_blood(page, bank_password, character_name):
    page.goto("https://seal-centoria.com/webshop?showItem=Proof%20of%20Blood")
    page.wait_for_load_state("networkidle")
    page.locator("#buy-item").first.click()
    page.wait_for_load_state("networkidle")
   
    page.locator("input[placeholder='Bank Password']").first.fill(bank_password)
    modal_buy_button = page.locator(".modal-content button:has-text('Buy'), .modal-footer button:has-text('Buy')").first
    modal_buy_button.click()

    verify_transaction_status(page, character_name, "Proof of Blood")


# =====================================================================
# MODULE: NORMAL DAILY LOGIN ATTENDANCE ROUTINE
# =====================================================================
def claim_normal_daily_login(page, character_name):
    print("🌐 **Opening dashboard management portal for Normal Daily Login...**")
    page.goto("https://seal-centoria.com/member/manage", wait_until="domcontentloaded")
    
    # Step 1: Wait for and trigger the Main 'Game' Tab
    game_tab_nav = page.locator("ul.nav-tabs a[href='#game']").first
    game_tab_nav.wait_for(state="attached", timeout=10000)
    
    print("🎯 **Selecting main 'Game' tab panel view...**")
    page.evaluate("jQuery(\"a[href='#game']\").tab('show');")
    page.wait_for_timeout(1500)

    # Step 2: Interfacing with the inner sub-navigation tabs
    try:
        print("🔍 **Locating inner 'Daily Login' sub-tab navigation...**")
        sub_tab_daily_login = page.locator("#game a:has-text('Daily Login'), #game ul.nav-tabs a:has-text('Daily Login')").first
        sub_tab_daily_login.wait_for(state="visible", timeout=5000)
        sub_tab_daily_login.click()
        page.wait_for_timeout(1500)
        print("📂 **Inner 'Daily Login' view successfully active.**")
        
    except Exception as sub_tab_err:
        print(f"⚠️ **[SUB-TAB FAILURE]:** Could not switch to the inner Daily Login tab: `{sub_tab_err}`. Aborting execution.")
        return

    # 🌟 CRITICAL FIX: Define the button pointer immediately so it is available globally within this scope!
    daily_claim_button = page.locator("#game button#manageButton[data-api='daily-login-claim']:not([disabled]):has-text('Claim')").first

    # Step 3: Hardened Selectric Dropdown Interface
    try:
        print(f"📦 **Verifying character selection framework for: `{character_name}`...**")
        dropdown_trigger = page.locator("#game .selectric-wrapper .selectric").first
        dropdown_trigger.wait_for(state="visible", timeout=5000)
        dropdown_trigger.click()
        page.wait_for_timeout(1000)
        
        character_option = page.locator(f"#game .selectric-items li:has-text('{character_name}')").first
        character_option.wait_for(state="visible", timeout=5000)
        character_option.click()
        page.wait_for_timeout(1500)
        
    except Exception as dropdown_err:
        send_to_discord(f"⚠️ **[DROPDOWN ENHANCEMENT NOTICE]:** `{dropdown_err}`. Proceeding to check claim element visibility...")

    # Step 4: Target and Submit the Active Claim Button
    # Re-verify count now that the dropdown actions are completed
    if daily_claim_button.count() == 0:
        send_to_discord(f"⏩ **[Daily Login]:** No active, uncompleted claim buttons found. Attendance may already be fully processed for `{character_name}` today.")
        return

    max_attempts = 3
    attempt = 1
    
    while attempt <= max_attempts:
        print(f"👆 **[Daily Attendance]:** Submitting login registration for `{character_name}` [Attempt {attempt}/{max_attempts}]...")
        
        daily_claim_button.scroll_into_view_if_needed()
        daily_claim_button.click()
        
        status_report = verify_transaction_status(page, character_name, "Normal Daily Attendance")
        
        if status_report == "RETRY_CAPTCHA":
            print("🔄 **[RETRY ACTUATOR]:** Token synchronization miss. Cooling down 10s before retry loop...")
            page.wait_for_timeout(10000)
            attempt += 1
        elif status_report is True:
            break
        else:
            print("⏳ **[Toast Timeout/Bypass]:** Toast not detected in main scope. Executing physical page state verification...")
            page.wait_for_timeout(2000)
            
            # Use the global state check for verification fallback
            claimed_check = page.locator("#game button#manageButton[data-api='daily-login-claim'][disabled]:has-text('Claimed')").first
            
            if claimed_check.count() > 0:
                print(f"✅ **[Daily Attendance SUCCESS]** ({character_name}): Attendance verified successfully via button state transformation! Skipping toast reliance.")
                send_to_discord(f"✅ **[Daily Attendance SUCCESS]** ({character_name}): Attendance verified successfully via button state transformation! Skipping toast reliance.")
                break
            else:
                send_to_discord("❌ **[Verification Failure]:** Button is still active and un-claimed. Proceeding with remaining retry parameters...")
                attempt += 1


# =====================================================================
# SEASONAL DAILY LOGIN EVENT ROUTINE (Gated behind Captcha)
# =====================================================================
def claim_daily_login_events(page, character_name):
    print("🌐 Navigating directly to the management dashboard...")
    page.goto("https://seal-centoria.com/member/manage", wait_until="domcontentloaded")
    
    print("⏳ Waiting for core panel components to render...")
    main_nav_tabs = page.locator("ul.nav-tabs:has(a[href='#login-events'])").first
    main_nav_tabs.wait_for(state="attached", timeout=10000)
    
    print("🛡️ Verifying Cloudflare Turnstile token status...")
    try:
        turnstile_iframe = page.locator("iframe[src*='challenges.cloudflare.com']").first
        if turnstile_iframe.count() > 0:
            turnstile_iframe.wait_for(state="visible", timeout=3000)
            captcha_success_badge = page.locator(".cf-turnstile:has-text('Success!'), body:has-text('Success!')").first
            captcha_success_badge.wait_for(state="attached", timeout=10000)
            print("✅ Cloudflare token successfully serialized into form context!")
    except Exception as ce:
        print(f"  ⚠️ Captcha check skipped/timed out: {ce}.")

    page.wait_for_timeout(1000)
    
    print("🎯 Forcing 'Login Events' tab switch via native Bootstrap API trigger...")
    try:
        page.evaluate("jQuery(\"a[href='#login-events']\").tab('show');")
        page.wait_for_timeout(1500)
    except Exception as je:
        print(f"  ⚠️ Tab execution bypass warning: {je}")
        page.evaluate("""() => {
            document.querySelectorAll('.tab-content .tab-pane').forEach(p => p.classList.remove('active', 'in'));
            const pane = document.querySelector('#login-events');
            if (pane) { pane.classList.add('active', 'in'); pane.style.display = 'block'; }
        }""")
        page.wait_for_timeout(1000)

    claim_elements = page.locator("#login-events .claim-rewards").all()
    element_count = len(claim_elements)
    
    if element_count == 0:
        print(f"  ⏩ [Login Event]: No claim components found inside the current panel view.")
        return

    print(f"  🔍 [Login Event]: Detected {element_count} active tracks. Commencing sequential claims...")
    
    for index, current_reward_box in enumerate(claim_elements):
        claim_id = current_reward_box.get_attribute("data-claim") or f"Index {index+1}"
        
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            print(f"  👆 [Milestone {index+1}/{element_count}]: Triggering claim sequence (ID: {claim_id}) [Attempt {attempt}/{max_attempts}]...")
            current_reward_box.evaluate("node => node.click()")
            status_report = verify_transaction_status(page, character_name, f"Login Milestone {claim_id}")
            
            if status_report == "RETRY_CAPTCHA":
                print(f"  🔄 [RETRY ACTUATOR]: Token missed. Cooling down 10s to clear anti-spam and refresh token...")
                page.wait_for_timeout(10000)
                attempt += 1
            else:
                break
        
        if index < element_count - 1:
            print("  ⏳ Enforcing 10-second backend anti-spam delay...")
            page.wait_for_timeout(10000)


# =====================================================================
# ENGINE RUNNER
# =====================================================================
def main():
    accounts_config = [
        {
            "username": os.getenv("CENTORIA_USER", ""),
            "password": os.getenv("CENTORIA_PASS", ""),
            "bank_pass": os.getenv("CENTORIA_BANK", ""),
            "char_name": os.getenv("CENTORIA_CHAR", ""),
            "want_dungeon_key": True,
            "want_quest_voucher": True,
            "want_proof_of_blood": True,
            # "want_abyssal_key": True,
            "want_normal_daily": True,
            "want_seasonal_claims": False
        },
        {
            "username": os.getenv("CENTORIA_USER_2", ""),
            "password": os.getenv("CENTORIA_PASS_2", ""),
            "bank_pass": os.getenv("CENTORIA_BANK_2", ""),
            "char_name": os.getenv("CENTORIA_CHAR_2", ""),
            "want_dungeon_key": True,
            "want_quest_voucher": True,
            "want_proof_of_blood": False,
            "want_normal_daily": True,
            "want_seasonal_claims": False
        },
        {
            "username": os.getenv("CENTORIA_USER_3", ""),
            "password": os.getenv("CENTORIA_PASS_3", ""),
            "bank_pass": os.getenv("CENTORIA_BANK_3", ""),
            "char_name": os.getenv("CENTORIA_CHAR_3", ""),
            "want_dungeon_key": True,
            "want_quest_voucher": True,
            "want_proof_of_blood": False,
            "want_normal_daily": True,
            "want_seasonal_claims": False
        },
        {
            "username": os.getenv("CENTORIA_USER_4", ""),
            "password": os.getenv("CENTORIA_PASS_4", ""),
            "bank_pass": os.getenv("CENTORIA_BANK_4", ""),
            "char_name": os.getenv("CENTORIA_CHAR_4", ""),
            "want_dungeon_key": True,
            "want_quest_voucher": True,
            "want_proof_of_blood": False,
            "want_normal_daily": True,
            "want_seasonal_claims": False
        },
    ]

    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), "playwright_stealth_profile")
        
        print("🚀 Launching secure persistent browser context shell...")
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        for account in accounts_config:
            if not account["username"]:
                continue
                
            print(f"\n👤 Account: {account['username']} ({account['char_name']})")
            send_to_discord("==================================================")
            send_to_discord(f"\n👤 Account: {account['username']} ({account['char_name']})")

            try:
                run_login(page, account["username"], account["password"])
                
                # Dynamic .get() selectors allow configuration files to remain minimal and clean
                if account.get("want_dungeon_key", False):
                    purchase_world_dungeon_key(page, account["bank_pass"], account["char_name"])

                if account.get("want_quest_voucher", False):
                    purchase_daily_quest_voucher(page, account["bank_pass"], account["char_name"])

                if account.get("want_proof_of_blood", False):
                    purchase_proof_of_blood(page, account["bank_pass"], account["char_name"])

                if account.get("want_abyssal_key", False):
                    purchase_abyssal_key(page, account["bank_pass"], account["char_name"])
                
                if account.get("want_normal_daily", False):
                    claim_normal_daily_login(page, account["char_name"])
                
                if account.get("want_seasonal_claims", False):
                    claim_daily_login_events(page, account["char_name"])
                
                print("🧼 Clearing session... Logging out account safely.")
                page.goto("https://seal-centoria.com/member/logout")
                page.wait_for_load_state("networkidle")
                
            except Exception as e:
                print(f"  ❌ [CRITICAL SYSTEM ERROR]: Failed to execute routine -> {e}")
                send_to_discord(f"  ❌ [CRITICAL SYSTEM ERROR]: Failed to execute routine -> {e}")
                page.goto("https://seal-centoria.com/member/logout")
                
        print("\n🏁 All processes finished. Environment shutting down cleanly.")

        final_report = "\n🏁 **All processes finished. Environment shutting down cleanly.**"

        if DISCORD_USER_ID:
            final_report += f"\n🔔 Daily webshop purchase done <@{DISCORD_USER_ID}>."
        send_to_discord(final_report)
        context.close()

if __name__ == "__main__":
    main()