# modules/kitchen.py — KITCHEN DISPLAY SYSTEM v1.0
import streamlit as st
import pandas as pd
import json
import time
import logging
from datetime import datetime

from database import run_query, run_action, get_setting
from utils import get_baku_now, log_system

logger = logging.getLogger(__name__)


def render_kitchen_page():
    """Mətbəx / Barista Display — Real-time sifariş ekranı"""

    st.markdown("""
    <style>
    /* Kitchen Display Override */
    .kitchen-header {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        padding: 15px 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kh-title { font-size: 22px; font-weight: 900; color: #FFF; }
    .kh-time { font-size: 16px; color: #888; font-weight: 700; }
    .kh-stats { display: flex; gap: 15px; }
    .kh-stat { text-align: center; }
    .kh-stat-num { font-size: 28px; font-weight: 900; }
    .kh-stat-label { font-size: 11px; color: #888; font-weight: 600; }

    /* Order Cards */
    .ko-card {
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 5px solid;
        position: relative;
        transition: all 0.2s;
    }
    .ko-new {
        background: linear-gradient(135deg, #fff3e0, #ffe0b2);
        border-color: #FF9800;
    }
    .ko-preparing {
        background: linear-gradient(135deg, #e3f2fd, #bbdefb);
        border-color: #2196F3;
    }
    .ko-urgent {
        background: linear-gradient(135deg, #ffebee, #ffcdd2);
        border-color: #f44336;
        animation: urgentPulse 1.5s infinite;
    }
    @keyframes urgentPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(244,67,54,0.3); }
        50% { box-shadow: 0 0 0 8px rgba(244,67,54,0); }
    }
    .ko-done {
        background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
        border-color: #4CAF50;
        opacity: 0.7;
    }

    .ko-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .ko-id { font-weight: 900; font-size: 18px; color: #333; }
    .ko-time-badge { 
        padding: 4px 10px; 
        border-radius: 20px; 
        font-size: 12px; 
        font-weight: 800; 
        color: #FFF;
    }
    .ko-time-ok { background: #4CAF50; }
    .ko-time-warn { background: #FF9800; }
    .ko-time-late { background: #f44336; }

    .ko-source { font-size: 12px; color: #888; font-weight: 600; margin-bottom: 8px; }
    .ko-items { margin: 10px 0; }
    .ko-item-row { 
        display: flex; 
        justify-content: space-between; 
        padding: 6px 0; 
        border-bottom: 1px dashed #ddd; 
        font-size: 15px;
    }
    .ko-item-name { font-weight: 700; color: #333; }
    .ko-item-qty { 
        background: #333; 
        color: #FFF; 
        padding: 2px 10px; 
        border-radius: 10px; 
        font-weight: 900; 
        font-size: 14px;
    }
    .ko-notes { 
        background: rgba(0,0,0,0.05); 
        padding: 8px 12px; 
        border-radius: 8px; 
        font-size: 13px; 
        color: #666; 
        margin-top: 8px;
        font-style: italic;
    }
    </style>
    """, unsafe_allow_html=True)

    # ============================================================
    # HEADER
    # ============================================================
    now = get_baku_now()

    # Statistikalar
    new_count = 0
    prep_count = 0
    done_count = 0
    try:
        stats = run_query("""
            SELECT status, COUNT(*) as cnt 
            FROM kitchen_orders 
            WHERE DATE(created_at) = DATE(:now)
            GROUP BY status
        """, {"now": now})
        for _, row in stats.iterrows():
            if row['status'] == 'NEW':
                new_count = row['cnt']
            elif row['status'] == 'PREPARING':
                prep_count = row['cnt']
            elif row['status'] == 'DONE':
                done_count = row['cnt']
    except:
        pass

    st.markdown(f"""
    <div class="kitchen-header">
        <div>
            <div class="kh-title">🍳 MƏTBƏX / BARİSTA</div>
        </div>
        <div class="kh-stats">
            <div class="kh-stat">
                <div class="kh-stat-num" style="color:#FF9800;">{new_count}</div>
                <div class="kh-stat-label">YENİ</div>
            </div>
            <div class="kh-stat">
                <div class="kh-stat-num" style="color:#2196F3;">{prep_count}</div>
                <div class="kh-stat-label">HAZIRLANAN</div>
            </div>
            <div class="kh-stat">
                <div class="kh-stat-num" style="color:#4CAF50;">{done_count}</div>
                <div class="kh-stat-label">HAZIR</div>
            </div>
        </div>
        <div class="kh-time">{now.strftime('%H:%M')}</div>
    </div>
    """, unsafe_allow_html=True)

    # Auto refresh
    auto_refresh = st.toggle("🔄 Avtomatik Yenilə (10 san)", value=True, key="kitchen_auto")

    # ============================================================
    # AKTİV SİFARİŞLƏR
    # ============================================================
    orders = run_query("""
        SELECT * FROM kitchen_orders 
        WHERE status IN ('NEW', 'PREPARING')
        AND DATE(created_at) = DATE(:now)
        ORDER BY 
            CASE WHEN priority='URGENT' THEN 0 ELSE 1 END,
            CASE WHEN status='PREPARING' THEN 0 ELSE 1 END,
            created_at ASC
    """, {"now": now})

    if orders.empty:
        st.markdown("""
        <div style="text-align:center; padding: 80px 20px;">
            <div style="font-size: 80px; margin-bottom: 20px;">☕</div>
            <div style="font-size: 24px; font-weight: 900; color: #666;">Yeni sifariş gözlənilir...</div>
            <div style="font-size: 14px; color: #999; margin-top: 10px;">Sifarişlər avtomatik burada görünəcək</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Grid layout
        cols = st.columns(3)
        for idx, (_, order) in enumerate(orders.iterrows()):
            with cols[idx % 3]:
                render_kitchen_order_card(order, now)

    # ============================================================
    # TAMAMLANMIŞ SİFARİŞLƏR
    # ============================================================
    with st.expander(f"✅ Tamamlanmış Sifarişlər ({done_count})", expanded=False):
        done_orders = run_query("""
            SELECT * FROM kitchen_orders 
            WHERE status = 'DONE'
            AND DATE(created_at) = DATE(:now)
            ORDER BY completed_at DESC
            LIMIT 20
        """, {"now": now})

        if not done_orders.empty:
            for _, order in done_orders.iterrows():
                try:
                    items = json.loads(order['items'])
                    items_str = ", ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
                except:
                    items_str = str(order['items'])[:50]

                completed_time = ""
                if order.get('completed_at') and order.get('created_at'):
                    try:
                        diff_min = int((order['completed_at'] - order['created_at']).total_seconds() / 60)
                        completed_time = f" ({diff_min} dəq)"
                    except:
                        pass

                st.markdown(f"""
                <div class="ko-card ko-done">
                    <div class="ko-header">
                        <div class="ko-id">#{order['id']}</div>
                        <div style="font-size:12px; color:#666;">✅ Hazır{completed_time}</div>
                    </div>
                    <div style="font-size:13px; color:#555;">{items_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Bu gün tamamlanmış sifariş yoxdur.")

    # Auto-refresh
    if auto_refresh:
        time.sleep(10)
        st.rerun()


def render_kitchen_order_card(order, now):
    """Tək sifariş kartı render"""
    order_id = order['id']
    status = order['status']
    priority = order.get('priority', 'NORMAL')

    # Keçən vaxt
    elapsed_min = 0
    try:
        elapsed = now - order['created_at']
        if hasattr(elapsed, 'total_seconds'):
            elapsed_min = int(elapsed.total_seconds() / 60)
        else:
            elapsed_min = 0
    except:
        elapsed_min = 0

    # Vaxt badge
    if elapsed_min < 5:
        time_css = "ko-time-ok"
        time_text = f"{elapsed_min} dəq"
    elif elapsed_min < 10:
        time_css = "ko-time-warn"
        time_text = f"⚠️ {elapsed_min} dəq"
    else:
        time_css = "ko-time-late"
        time_text = f"🔥 {elapsed_min} dəq!"

    # Card CSS
    if priority == 'URGENT':
        card_css = "ko-urgent"
    elif status == 'PREPARING':
        card_css = "ko-preparing"
    else:
        card_css = "ko-new"

    # Items parse
    try:
        items = json.loads(order['items'])
    except:
        items = [{"item_name": str(order['items'])[:30], "qty": 1}]

    items_html = ""
    for item in items:
        items_html += f"""
        <div class="ko-item-row">
            <span class="ko-item-name">{item['item_name']}</span>
            <span class="ko-item-qty">×{item['qty']}</span>
        </div>"""

    # Source
    source = order.get('sale_source', 'POS')
    table_label = order.get('table_label', '')
    source_text = f"🍽️ {table_label}" if table_label else f"🏃 {source}"

    # Notes
    notes_html = ""
    if order.get('notes'):
        notes_html = f'<div class="ko-notes">📝 {order["notes"]}</div>'

    # Status badge
    status_emoji = "🆕" if status == 'NEW' else "👨‍🍳"

    st.markdown(f"""
    <div class="ko-card {card_css}">
        <div class="ko-header">
            <div class="ko-id">{status_emoji} #{order_id}</div>
            <div class="ko-time-badge {time_css}">{time_text}</div>
        </div>
        <div class="ko-source">{source_text} · {order.get('created_by', '')}</div>
        <div class="ko-items">{items_html}</div>
        {notes_html}
    </div>
    """, unsafe_allow_html=True)

    # Action Buttons
    if status == 'NEW':
        c1, c2 = st.columns(2)
        if c1.button("👨‍🍳 Qəbul Et", key=f"accept_{order_id}", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET status='PREPARING', accepted_at=:t WHERE id=:id",
                {"t": now, "id": order_id}
            )
            log_system(st.session_state.user, f"KITCHEN_ACCEPT: #{order_id}")
            st.rerun()
        if c2.button("🚨 Təcili", key=f"urgent_{order_id}", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET priority='URGENT', status='PREPARING', accepted_at=:t WHERE id=:id",
                {"t": now, "id": order_id}
            )
            log_system(st.session_state.user, f"KITCHEN_URGENT: #{order_id}")
            st.rerun()
    elif status == 'PREPARING':
        if st.button("✅ HAZIRDIR!", key=f"done_{order_id}", type="primary", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET status='DONE', completed_at=:t, completed_by=:u WHERE id=:id",
                {"t": now, "u": st.session_state.user, "id": order_id}
            )
            log_system(st.session_state.user, f"KITCHEN_DONE: #{order_id}")
            st.rerun()
