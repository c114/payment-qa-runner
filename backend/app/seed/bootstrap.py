"""Seed default admin, workflow, page mappings, network profile, settings."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.models import (
    AdminUser, AccountCreationSettings, NetworkProfile, PageMapping,
    PayrailsConfig, RunnerSettings, WorkflowStep,
)

logger = logging.getLogger(__name__)

# Preply-like EXAMPLE selectors from screenshots — marked is_example=True; admin must edit.
# Environments are NOT seeded with preply.com.
PAGE_MAPPINGS = [
    # Page 1 - Home
    {"key": "home.login_btn", "label": "首页 - Log In", "page_group": "home", "selector_type": "text",
     "selector": "Log In", "is_example": True, "sort_order": 10,
     "help_zh": "首页右上角登录按钮（示例选择器，请按目标沙箱修改）"},
    # Page 2 - Login / signup choice
    {"key": "login.signup_student_link", "label": "登录页 - Sign up as a student", "page_group": "login",
     "selector_type": "text", "selector": "Sign up as a student", "is_example": True, "sort_order": 20,
     "help_zh": "登录弹层中的学生注册入口"},
    {"key": "login.email_input", "label": "登录 - 邮箱", "page_group": "login", "selector_type": "css",
     "selector": "input[type='email'], input[name='email']", "is_example": True, "sort_order": 21},
    {"key": "login.password_input", "label": "登录 - 密码", "page_group": "login", "selector_type": "css",
     "selector": "input[type='password'], input[name='password']", "is_example": True, "sort_order": 22},
    {"key": "login.submit_btn", "label": "登录 - 提交", "page_group": "login", "selector_type": "css",
     "selector": "button[type='submit']", "is_example": True, "sort_order": 23},
    # Page 3 - Signup form
    {"key": "signup.name_input", "label": "注册 - 姓名", "page_group": "signup", "selector_type": "css",
     "selector": "input[name='name'], input[autocomplete='name']", "is_example": True, "sort_order": 30},
    {"key": "signup.email_input", "label": "注册 - 邮箱", "page_group": "signup", "selector_type": "css",
     "selector": "input[type='email']", "is_example": True, "sort_order": 31},
    {"key": "signup.password_input", "label": "注册 - 密码", "page_group": "signup", "selector_type": "css",
     "selector": "input[type='password']", "is_example": True, "sort_order": 32},
    {"key": "signup.submit_btn", "label": "注册 - 提交", "page_group": "signup", "selector_type": "text",
     "selector": "Sign up", "is_example": True, "sort_order": 33},
    # Page 4 - User menu
    {"key": "nav.user_menu", "label": "用户菜单", "page_group": "nav", "selector_type": "css",
     "selector": "[data-qa-id='user-menu'], button[aria-label*='Account']", "is_example": True, "sort_order": 40},
    {"key": "nav.settings_link", "label": "设置入口", "page_group": "nav", "selector_type": "text",
     "selector": "Settings", "is_example": True, "sort_order": 41},
    # Page 5 - Settings sidebar
    {"key": "settings.payment_methods", "label": "设置 - Payment methods", "page_group": "settings",
     "selector_type": "text", "selector": "Payment methods", "is_example": True, "sort_order": 50},
    # Page 6 - Payment methods
    {"key": "payment.add_card_btn", "label": "添加卡片", "page_group": "payment", "selector_type": "text",
     "selector": "Add card", "is_example": True, "sort_order": 60},
    # Page 7 - Save card modal / Payrails iframe
    {"key": "payment.modal_title", "label": "弹窗标题 Save a payment card", "page_group": "payment",
     "selector_type": "text", "selector": "Save a payment card", "is_example": True, "sort_order": 70},
    {"key": "payment.payrails_iframe", "label": "Payrails iframe", "page_group": "payment",
     "selector_type": "css", "selector": "iframe[src*='payrails'], iframe[name*='payrails']",
     "is_example": True, "sort_order": 71, "help_zh": "Payrails 卡表单通常在 iframe 内"},
    {"key": "payment.card_number", "label": "卡号", "page_group": "payment", "selector_type": "css",
     "selector": "input[name='cardNumber'], input[autocomplete='cc-number']", "iframe_selector": "iframe[src*='payrails']",
     "is_example": True, "sort_order": 72},
    {"key": "payment.expiry", "label": "有效期", "page_group": "payment", "selector_type": "css",
     "selector": "input[name='expiry'], input[autocomplete='cc-exp']", "iframe_selector": "iframe[src*='payrails']",
     "is_example": True, "sort_order": 73},
    {"key": "payment.cvv", "label": "CVC/CVV", "page_group": "payment", "selector_type": "css",
     "selector": "input[name='cvc'], input[autocomplete='cc-csc']", "iframe_selector": "iframe[src*='payrails']",
     "is_example": True, "sort_order": 74, "help_zh": "CVV 仅内存填充，提交后立即丢弃，永不落库"},
    {"key": "payment.save_btn", "label": "Save card 按钮", "page_group": "payment", "selector_type": "text",
     "selector": "Save card", "is_example": True, "sort_order": 75},
    # Result / 3DS detection
    {"key": "result.success", "label": "成功提示", "page_group": "result", "selector_type": "text",
     "selector": "Card saved|Payment method added|Success", "is_example": True, "sort_order": 80},
    {"key": "result.declined", "label": "拒付提示", "page_group": "result", "selector_type": "text",
     "selector": "declined|Card declined|payment failed", "is_example": True, "sort_order": 81},
    {"key": "result.invalid_card", "label": "无效卡", "page_group": "result", "selector_type": "text",
     "selector": "invalid card|card number is invalid", "is_example": True, "sort_order": 82},
    {"key": "result.invalid_cvv", "label": "无效 CVV", "page_group": "result", "selector_type": "text",
     "selector": "invalid.*cvc|invalid.*cvv|security code", "is_example": True, "sort_order": 83},
    {"key": "result.insufficient_funds", "label": "余额不足", "page_group": "result", "selector_type": "text",
     "selector": "insufficient funds", "is_example": True, "sort_order": 84},
    {"key": "result.threeds", "label": "3DS 挑战", "page_group": "result", "selector_type": "css",
     "selector": "iframe[src*='3ds'], iframe[src*='acs'], [data-threeds], text=Verify your payment",
     "is_example": True, "sort_order": 85, "help_zh": "检测到 3DS 立即 FAIL 并结束用例，不求解 OTP"},
]

WORKFLOW_STEPS = [
    {"step_key": "open_home", "name_zh": "打开首页", "name_en": "Open home", "action": "navigate",
     "mapping_keys": [], "config": {"use_env_base_url": True}, "sort_order": 1},
    {"step_key": "click_login", "name_zh": "点击登录", "name_en": "Click Log In", "action": "click",
     "mapping_keys": ["home.login_btn"], "config": {}, "sort_order": 2},
    {"step_key": "login_or_signup", "name_zh": "登录或注册", "name_en": "Login or signup", "action": "fill",
     "mapping_keys": ["login.email_input", "login.password_input", "login.submit_btn"],
     "config": {"mode": "login"}, "sort_order": 3},
    {"step_key": "open_user_menu", "name_zh": "打开用户菜单", "name_en": "Open user menu", "action": "click",
     "mapping_keys": ["nav.user_menu"], "config": {}, "sort_order": 4},
    {"step_key": "open_settings", "name_zh": "进入设置", "name_en": "Open Settings", "action": "click",
     "mapping_keys": ["nav.settings_link"], "config": {}, "sort_order": 5},
    {"step_key": "open_payment_methods", "name_zh": "支付方式", "name_en": "Payment methods", "action": "click",
     "mapping_keys": ["settings.payment_methods"], "config": {}, "sort_order": 6},
    {"step_key": "click_add_card", "name_zh": "添加卡片", "name_en": "Add card", "action": "click",
     "mapping_keys": ["payment.add_card_btn"], "config": {}, "sort_order": 7},
    {"step_key": "fill_payrails_card", "name_zh": "填写 Payrails 卡信息", "name_en": "Fill Payrails card",
     "action": "fill_card", "mapping_keys": ["payment.payrails_iframe", "payment.card_number", "payment.expiry", "payment.cvv"],
     "config": {}, "sort_order": 8},
    {"step_key": "save_card", "name_zh": "保存卡片", "name_en": "Save card", "action": "click",
     "mapping_keys": ["payment.save_btn"], "config": {}, "sort_order": 9},
    {"step_key": "detect_result", "name_zh": "检测结果/3DS", "name_en": "Detect result/3DS", "action": "detect",
     "mapping_keys": ["result.success", "result.declined", "result.invalid_card", "result.invalid_cvv",
                      "result.insufficient_funds", "result.threeds"],
     "config": {}, "sort_order": 10},
]


def seed_all(db: Session) -> None:
    settings = get_settings()
    if db.query(AdminUser).count() == 0:
        db.add(AdminUser(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
        ))
        logger.info("Seeded admin user %s", settings.admin_email)

    if db.query(PageMapping).count() == 0:
        for m in PAGE_MAPPINGS:
            db.add(PageMapping(**m))
        logger.info("Seeded %d page mappings", len(PAGE_MAPPINGS))

    if db.query(WorkflowStep).count() == 0:
        for s in WORKFLOW_STEPS:
            db.add(WorkflowStep(**s))
        logger.info("Seeded %d workflow steps", len(WORKFLOW_STEPS))

    if db.query(NetworkProfile).filter_by(name="Direct").count() == 0:
        db.add(NetworkProfile(name="Direct", mode="direct", is_default=True))
        logger.info("Seeded Direct network profile")

    if db.query(RunnerSettings).count() == 0:
        db.add(RunnerSettings())
        logger.info("Seeded runner settings")

    if db.query(AccountCreationSettings).count() == 0:
        db.add(AccountCreationSettings(enabled=False, test_email_domain=""))
        logger.info("Seeded account creation settings (OFF)")

    if db.query(PayrailsConfig).count() == 0:
        db.add(PayrailsConfig(
            sandbox_base_url="",
            merchant_id="",
            api_key_enc="",
            public_key="",
            notes="Fill sandbox fields in admin panel. Do not invent API secrets.",
            sandbox_cards={},
            result_selectors={},
            threeds_selectors=[],
        ))
        logger.info("Seeded empty Payrails config")

    db.commit()
