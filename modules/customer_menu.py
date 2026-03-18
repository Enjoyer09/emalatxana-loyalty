# modules/customer_menu.py — PREMIUM REDESIGN v6.0
import streamlit as st
import pandas as pd
import json
import logging

from database import run_query, run_action, get_setting
from utils import get_baku_now

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from PIL import Image
except ImportError:
    Image = None


# ============================================================
# PREMIUM CSS
# ============================================================
def inject_customer_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jura:wght@600;700;800&family=Nunito:wght@400;600;700;800;900&display=swap');

    .stApp {
        background: linear-gradient(180deg, #F7F1EA 0%, #F2EAE1 100%) !important;
        color: #2D241F !important;
        font-family: 'Nunito', sans-serif !important;
    }
    header, #MainMenu, footer, div[data-testid="stStatusWidget"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section.main > div:first-child { padding-top: 0 !important; }

    /* HERO */
    .hero-wrap {
        background: radial-gradient(circle at top left, rgba(255,255,255,0.08) 0%, transparent 35%),
                    linear-gradient(160deg, #2E1F17 0%, #4A3023 55%, #7A523A 100%);
        padding: 30px 20px 50px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .hero-wrap::after {
        content: '';
        position: absolute;
        bottom: -22px;
        left: 0;
        right: 0;
        height: 44px;
        background: #F7F1EA;
        border-radius: 50% 50% 0 0 / 100% 100% 0 0;
    }
    .hero-icon {
        font-size: 40px;
        margin-bottom: 6px;
    }
    .hero-brand {
        font-family: 'Jura', sans-serif;
        font-weight: 800;
        font-size: 24px;
        color: #F5E2C8;
        letter-spacing: 3px;
        text-transform: uppercase;
    }
    .hero-sub {
        color: rgba(245,226,200,0.75);
        font-size: 13px;
        margin-top: 6px;
        font-weight: 600;
    }

    /* LOYALTY CARD */
    .club-card {
        background: linear-gradient(145deg, #FFFFFF 0%, #FCFAF8 100%);
        border: 1px solid #E8DDD1;
        border-radius: 28px;
        margin: 0 16px 16px;
        margin-top: -15px;
        padding: 22px 18px;
        box-shadow: 0 12px 35px rgba(50,30,20,0.08);
        position: relative;
        overflow: hidden;
    }
    .club-card::before {
        content: '☕';
        position: absolute;
        right: -5px;
        top: -5px;
        font-size: 90px;
        opacity: 0.05;
    }
    .cc-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .cc-title {
        font-family: 'Jura', sans-serif;
        font-size: 17px;
        font-weight: 800;
        color: #3A271D;
        letter-spacing: 1px;
    }
    .cc-tier {
        background: linear-gradient(135deg, #3A271D, #5C3A28);
        color: #F6E8D7;
        padding: 5px 12px;
        border-radius: 16px;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 1px;
    }
    .cc-desc {
        color: #9A8B7F;
        font-size: 12px;
        margin-bottom: 16px;
        font-weight: 600;
    }

    /* STAMP GRID */
    .stamp-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
        max-width: 290px;
        margin: 0 auto 14px;
    }
    .stamp {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: 13px;
        transition: all 0.3s ease;
    }
    .stamp-empty {
        background: #F5F0EB;
        border: 2px solid #D9CEC1;
        color: #C8B9AA;
    }
    .stamp-filled {
        background: linear-gradient(145deg, #3A271D, #56392A);
        border: 2px solid #3A271D;
        color: #F5E2C8;
        box-shadow: 0 3px 10px rgba(58,39,29,0.25);
    }
    .stamp-gift {
        background: linear-gradient(145deg, #E88D48, #D87431);
        border: 2px solid #E88D48;
        color: white;
        box-shadow: 0 4px 14px rgba(232,141,72,0.35);
        animation: pulseGift 1.8s infinite;
    }
    @keyframes pulseGift {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.08); }
    }
    .cc-footer {
        text-align: center;
        color: #A09184;
        font-size: 12px;
        font-weight: 700;
    }

    /* FREE ALERT */
    .free-coffee-banner {
        margin: 0 16px 14px;
        padding: 14px 16px;
        border-radius: 18px;
        background: linear-gradient(135deg, #E88D48, #F0A55E);
        color: white;
        text-align: center;
        font-weight: 900;
        font-size: 15px;
        box-shadow: 0 6px 20px rgba(232,141,72,0.28);
    }

    /* NOTIFICATION / HH BANNER */
    .smart-banner {
        margin: 0 16px 12px;
        padding: 12px 16px;
        border-radius: 16px;
        text-align: center;
        font-size: 13px;
        font-weight: 800;
    }
    .smart-banner.hh {
        background: linear-gradient(90deg, #FF6B35, #F7C948);
        color: #241A12;
        box-shadow: 0 4px 14px rgba(255,107,53,0.25);
    }
    .smart-banner.notif {
        background: linear-gradient(90deg, #7A523A, #A36A47);
        color: #FFF7F0;
        box-shadow: 0 4px 14px rgba(122,82,58,0.25);
    }

    /* REWARD BLOCKS */
    .reward-box {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 18px;
        margin: 0 16px 10px;
        padding: 14px 16px;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .reward-icon {
        width: 46px;
        height: 46px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
    }
    .reward-icon.coffee { background: #F4E8DB; }
    .reward-icon.gift { background: #FFF1E4; }
    .reward-title { font-weight: 800; font-size: 14px; color: #3A271D; }
    .reward-desc { font-size: 12px; color: #A09184; margin-top: 2px; }
    .reward-right { margin-left: auto; font-weight: 900; color: #3A271D; font-size: 16px; }

    /* SECTION TITLE */
    .section-title {
        font-family: 'Jura', sans-serif;
        font-size: 15px;
        font-weight: 800;
        color: #3A271D;
        margin: 16px 16px 8px;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* MENU */
    .menu-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        padding: 0 16px;
        margin-bottom: 8px;
    }
    .menu-card {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 18px;
        padding: 14px 12px;
        text-align: center;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .menu-emoji {
        font-size: 32px;
        margin-bottom: 6px;
    }
    .menu-name {
        font-size: 13px;
        font-weight: 800;
        color: #2D241F;
        line-height: 1.35;
        margin-bottom: 4px;
    }
    .menu-price {
        font-size: 17px;
        font-weight: 900;
        color: #3A271D;
    }
    .menu-badge {
        font-size: 10px;
        font-weight: 700;
        color: #D4763A;
        background: #FFF3E8;
        padding: 2px 8px;
        border-radius: 10px;
        margin-top: 6px;
        display: inline-block;
        align-self: center;
    }

    /* HISTORY */
    .history-card {
        background: #FFF;
        border: 1px solid #E8DDD1;
        border-radius: 16px;
        margin: 0 16px 8px;
        padding: 14px;
        border-left: 4px solid #3A271D;
    }
    .history-date {
        font-size: 11px;
        color: #B0A195;
        font-weight: 700;
    }
    .history-items {
        font-size: 13px;
        color: #5A4C42;
        line-height: 1.45;
        margin-top: 4px;
    }
    .history-total {
        font-size: 15px;
        color: #3A271D;
        font-weight: 900;
        margin-top: 6px;
    }
    .history-stamp {
        display: inline-block;
        margin-top: 6px;
        background: #F4E8DB;
        color: #3A271D;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: 800;
    }

    /* AI CHAT */
    .chat-bubble {
        padding: 12px 16px;
        border-radius: 18px;
        margin-bottom: 8px;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.5;
    }
    .chat-user {
        background: #3A271D;
        color: #F5E2C8;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        font-weight: 700;
    }
    .chat-ai {
        background: #FFF;
        border: 1px solid #E8DDD1;
        color: #3A271D;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }

    /* FORTUNE */
    .fortune-zone {
        border: 2px dashed #D9CEC1;
        border-radius: 22px;
        background: #FFF;
        margin: 16px;
        padding: 30px 20px;
        text-align: center;
    }
    .fortune-result {
        background: #FFF;
        border: 2px solid #E88D48;
        border-radius: 20px;
        padding: 20px;
        margin: 16px;
    }

    /* Streamlit overrides */
    h1, h2, h3, h4 { color: #2D241F !important; }
    div[data-baseweb="input"] > div {
        background: #FFF !important;
        border: 2px solid #E8DDD1 !important;
        border-radius: 14px !important;
        box-shadow: none !important;
    }
    div[data-baseweb="input"] input {
        color: #2D241F !important;
        font-weight: 600 !important;
        -webkit-text-fill-color: #2D241F !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #C5B7AA !important;
        -webkit-text-fill-color: #C5B7AA !important;
    }

    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #3A271D, #5C3A28) !important;
        border: none !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 15px rgba(58,39,29,0.2) !important;
        min-height: auto !important;
    }
    button[kind="primary"] p, button[kind="primaryFormSubmit"] p {
        color: #F5E2C8 !important;
        font-weight: 900 !important;
        font-size: 15px !important;
    }

    button[kind="secondary"], button[kind="secondaryFormSubmit"] {
        background: #FFF !important;
        border: 1px solid #E8DDD1 !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
        min-height: auto !important;
    }
    button[kind="secondary"] p {
        color: #3A271D !important;
        font-weight: 700 !important;
        font-size: 14px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #FFF;
        border-radius: 14px;
        padding: 4px;
        margin: 0 16px 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #E8DDD1;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 11px !important;
        color: #999 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        padding: 8px 4px !important;
    }
    .stTabs [aria-selected="true"] {
        background: #3A271D !important;
        color: #F5E2C8 !important;
        font-weight: 900 !important;
    }

    div[role="radiogroup"] > label {
        background: #FFF !important;
        border: 1px solid #E8DDD1 !important;
        border-radius: 10px !important;
        padding: 6px 12px !important;
        box-shadow: none !important;
        min-height: auto !important;
    }
    div[role="radiogroup"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"] > label p {
        color: #88796E !important;
        font-size: 12px !important;
        font-weight: 700 !important;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #3A271D !important;
        border-color: #3A271D !important;
        transform: none !important;
        box-shadow: none !important;
    }
    div[role="radiogroup"] label:has(input:checked) p {
        color: #F5E2C8 !important;
    }

    div[role="dialog"] > div {
        background: #F7F1EA !important;
        border: 2px solid #3A271D !important;
        border-radius: 22px !important;
    }

    .stFileUploader > div {
        background: #FFF !important;
        border: 2px dashed #D9CEC1 !important;
        border-radius: 16px !important;
    }

    ::-webkit-scrollbar { width: 0px; }
    </style>
    """, unsafe_allow_html=True)
