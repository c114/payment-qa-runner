"""Local Sandbox Payment Simulator for Payment Test Runner 2.0.0.

Simulates: Login → Payment Methods → Add Card → Fill → Submit → Result
Outcomes driven by card number last4 / magic prefixes:
  *4242 → BOUND
  *0002 → DECLINED
  *0003 → 3DS_REQUIRED
  *0001 → INVALID_DATA
  *9999 → DELAYED_REDIRECT (then BOUND)
  *0000 → TIMEOUT (slow then error)
Any other → UNKNOWN_RESULT page (worker must map to ERROR/UNKNOWN_RESULT)
"""
from __future__ import annotations

import secrets
import time
from typing import Optional

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Local Payment Sandbox", version="2.0.0")

# In-memory sessions: token → email
SESSIONS: dict[str, str] = {}
# Valid demo accounts (password always "password" or any non-empty for sandbox)
DEMO_PASSWORD_OK = True

LAYOUT = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;background:#0f1419;color:#e7ecf3}}
a{{color:#5b9fd4}} .card{{background:#1a2332;border:1px solid #2a3548;border-radius:10px;padding:24px;margin:16px 0}}
input,button{{font-size:16px;padding:10px 12px;border-radius:6px;border:1px solid #3a465c;background:#0c1017;color:#e7ecf3;width:100%;box-sizing:border-box;margin:6px 0}}
button{{background:#2d6cdf;border:none;cursor:pointer;font-weight:600}}
button:hover{{background:#3d7cef}} .err{{color:#f87171}} .ok{{color:#34d399}}
h1{{font-size:1.4rem}} h2{{font-size:1.1rem;margin-top:0}}
.muted{{color:#94a3b8;font-size:.9rem}}
</style></head><body>
{body}
</body></html>"""


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(LAYOUT.format(title=title, body=body))


def _email(request: Request) -> Optional[str]:
    tok = request.cookies.get("sandbox_session")
    if tok and tok in SESSIONS:
        return SESSIONS[tok]
    return None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    email = _email(request)
    if email:
        return RedirectResponse("/settings/payments", status_code=302)
    return page("Sandbox", """
<div class="card">
<h1>Local Payment Sandbox</h1>
<p class="muted">Payment Test Runner 2.0 — 本地绑卡沙箱</p>
<p><a href="/login">Log In</a></p>
</div>""")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/settings/payments"):
    if _email(request):
        return RedirectResponse(next or "/settings/payments", status_code=302)
    return page("Login", f"""
<div class="card">
<h1>Log In</h1>
<form method="post" action="/login" id="login-form">
<input type="hidden" name="next" value="{next}"/>
<label>Email</label>
<input type="email" name="email" id="email" data-testid="email" required placeholder="qa@example.com"/>
<label>Password</label>
<input type="password" name="password" id="password" data-testid="password" required/>
<button type="submit" data-testid="login-submit">Log In</button>
</form>
<p class="muted">任意邮箱 + 非空密码即可登录（沙箱）</p>
</div>""")


@app.post("/login")
def login_submit(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/settings/payments"),
):
    if not email or "@" not in email:
        return page("Login", """<div class="card"><p class="err" data-testid="login-error">Invalid email</p>
<p><a href="/login">Back</a></p></div>""")
    if not password:
        return page("Login", """<div class="card"><p class="err" data-testid="login-error">Bad credentials</p>
<p><a href="/login">Back</a></p></div>""")
    # Magic bad credential email
    if email.lower().startswith("bad@"):
        return page("Login", """<div class="card"><p class="err" data-testid="login-error">Bad credentials</p>
<p><a href="/login">Back</a></p></div>""")
    tok = secrets.token_urlsafe(24)
    SESSIONS[tok] = email.lower()
    resp = RedirectResponse(next or "/settings/payments", status_code=302)
    resp.set_cookie("sandbox_session", tok, httponly=True, samesite="lax")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("sandbox_session")
    return resp


@app.get("/settings/payments", response_class=HTMLResponse)
def payments(request: Request):
    email = _email(request)
    if not email:
        return RedirectResponse("/login?next=/settings/payments", status_code=302)
    return page("Payment methods", f"""
<div class="card">
<h1>Payment methods</h1>
<p class="muted">Signed in as {email}</p>
<p data-testid="payment-methods">Your saved payment methods</p>
<p><a href="/settings/payments/add" data-testid="add-card"><button type="button">Add card</button></a></p>
<p><a href="/logout">Log out</a></p>
</div>""")


@app.get("/settings/payments/add", response_class=HTMLResponse)
def add_card(request: Request):
    email = _email(request)
    if not email:
        return RedirectResponse("/login?next=/settings/payments/add", status_code=302)
    return page("Save a payment card", """
<div class="card">
<h1 data-testid="modal-title">Save a payment card</h1>
<form method="post" action="/settings/payments/submit" id="card-form">
<label>Card number</label>
<input name="number" id="card-number" data-testid="card-number" autocomplete="cc-number"
  placeholder="4242 4242 4242 4242" required/>
<label>Expiry (MM/YY)</label>
<input name="expiry" id="expiry" data-testid="expiry" autocomplete="cc-exp" placeholder="12/30" required/>
<label>CVC</label>
<input name="cvc" id="cvc" data-testid="cvc" autocomplete="cc-csc" placeholder="123" required/>
<button type="submit" data-testid="save-card">Save card</button>
</form>
<p class="muted">Magic last4: 4242=BOUND · 0002=DECLINED · 0003=3DS · 0001=INVALID · 9999=DELAYED · 0000=TIMEOUT</p>
</div>""")


def _outcome_from_pan(number: str) -> str:
    digits = "".join(c for c in number if c.isdigit())
    last4 = digits[-4:] if len(digits) >= 4 else ""
    mapping = {
        "4242": "BOUND",
        "0002": "DECLINED",
        "0003": "3DS_REQUIRED",
        "0001": "INVALID_DATA",
        "9999": "DELAYED_REDIRECT",
        "0000": "TIMEOUT",
    }
    return mapping.get(last4, "UNKNOWN")


@app.post("/settings/payments/submit", response_class=HTMLResponse)
async def submit_card(
    request: Request,
    number: str = Form(...),
    expiry: str = Form(...),
    cvc: str = Form(...),
):
    email = _email(request)
    if not email:
        return RedirectResponse("/login", status_code=302)

    digits = "".join(c for c in number if c.isdigit())
    if len(digits) < 13:
        return page("Result", """<div class="card"><h1 class="err" data-testid="result">INVALID_DATA</h1>
<p data-testid="result-reason">Card number is invalid</p>
<p><a href="/settings/payments/add">Try again</a></p></div>""")

    outcome = _outcome_from_pan(number)

    if outcome == "TIMEOUT":
        time.sleep(35)
        return page("Result", """<div class="card"><h1 class="err" data-testid="result">TIMEOUT</h1>
<p data-testid="result-reason">Request timed out</p></div>""")

    if outcome == "DELAYED_REDIRECT":
        time.sleep(3)
        return RedirectResponse("/settings/payments/result?code=BOUND", status_code=302)

    return RedirectResponse(f"/settings/payments/result?code={outcome}", status_code=302)


@app.get("/settings/payments/result", response_class=HTMLResponse)
def result_page(request: Request, code: str = "UNKNOWN"):
    email = _email(request)
    if not email:
        return RedirectResponse("/login", status_code=302)

    code = (code or "UNKNOWN").upper()
    if code == "BOUND":
        return page("Result", """<div class="card"><h1 class="ok" data-testid="result">BOUND</h1>
<p data-testid="result-reason">Card saved successfully</p>
<p data-testid="success">Payment method added</p>
<p><a href="/settings/payments">Back to Payment methods</a></p></div>""")
    if code == "DECLINED":
        return page("Result", """<div class="card"><h1 class="err" data-testid="result">DECLINED</h1>
<p data-testid="result-reason">Card declined</p>
<p><a href="/settings/payments/add">Try again</a></p></div>""")
    if code == "3DS_REQUIRED":
        return page("3DS", """<div class="card"><h1 data-testid="result">3DS_REQUIRED</h1>
<p data-testid="result-reason">Verify your payment</p>
<iframe data-testid="threeds" src="/3ds-frame" style="width:100%;height:120px;border:1px solid #3a465c"></iframe>
<p class="muted">Sandbox will not complete 3DS — runner must FAIL/3DS_REQUIRED</p></div>""")
    if code == "INVALID_DATA":
        return page("Result", """<div class="card"><h1 class="err" data-testid="result">INVALID_DATA</h1>
<p data-testid="result-reason">invalid card number</p></div>""")
    return page("Result", f"""<div class="card"><h1 data-testid="result">UNKNOWN</h1>
<p data-testid="result-reason">Unrecognized outcome: {code}</p></div>""")


@app.get("/3ds-frame", response_class=HTMLResponse)
def threeds_frame():
    return HTMLResponse("<html><body style='background:#111;color:#eee;font-family:sans-serif'>3-D Secure challenge (sandbox stub)</body></html>")


@app.get("/health")
def health():
    return {"status": "OK", "service": "sandbox", "version": "2.0.0"}
