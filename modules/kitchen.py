# modules/kitchen.py — FINAL PATCHED v2.0
import streamlit as st
import pandas as pd
import json
import time
import logging

from database import run_query, run_action
from utils import get_baku_now, log_system

logger = logging.getLogger(__name__)


def render_kitchen_page():
    st.markdown("""
    <style>
    .kds-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 18px 20px;
        border-radius: 16px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid #0f3460;
    }
    .kds-title { font-size: 20px; font-weight: 900; color: #FFF; font-family: 'Jura', sans-serif; }
    .kds-stats { display: flex; gap: 20px; }
    .kds-stat { text-align: center; }
    .kds-num { font-size: 26px; font-weight: 900; font-family: 'Jura', sans-serif; }
    .kds-label { font-size: 10px; color: #888; font-weight: 700; letter-spacing: 1px; }
    .kds-time { font-size: 14px; color: #666; font-weight: 700; }

    .ko-card { border-radius: 16px; padding: 16px; margin-bottom: 12px; border-left: 5px solid; position: relative; }
    .ko-new { background: linear-gradient(135deg, #fff3e0, #ffe0b2); border-color: #FF9800; }
    .ko-preparing { background: linear-gradient(135deg, #e3f2fd, #bbdefb); border-color: #2196F3; }
    .ko-urgent { background: linear-gradient(135deg, #ffebee, #ffcdd2); border-color: #f44336; animation: urgentPulse 1.5s infinite; }
    .ko-done { background: linear-gradient(135deg, #e8f5e9, #c8e6c9); border-color: #4CAF50; opacity: 0.75; }

    @keyframes urgentPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(244,67,54,0.3); }
        50% { box-shadow: 0 0 0 8px rgba(244,67,54,0); }
    }

    .ko-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .ko-id { font-weight: 900; font-size: 18px; color: #333; }
    .ko-time-badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 800; color: #FFF; }
    .ko-ok { background: #4CAF50; }
    .ko-warn { background: #FF9800; }
    .ko-late { background: #f44336; }
    .ko-source { font-size: 12px; color: #777; font-weight: 600; margin-bottom: 8px; }
    .ko-items { margin: 8px 0; }
    .ko-item-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed #ddd; font-size: 14px; }
    .ko-item-name { font-weight: 700; color: #333; }
    .ko-item-qty { background: #333; color: #FFF; padding: 2px 10px; border-radius: 10px; font-weight: 900; font-size: 13px; }
    .ko-notes { background: rgba(0,0,0,0.06); padding: 8px 12px; border-radius: 8px; font-size: 12px; color: #666; margin-top: 8px; font-style: italic; }

    .done-item { background: #f9f9f9; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

    now = get_baku_now()
    new_count = 0
    prep_count = 0
    done_count = 0
    avg_time_min = 0

    try:
        stats = run_query("""
            SELECT status, COUNT(*) as cnt
            FROM kitchen_orders
            WHERE DATE(created_at) = DATE(:now)
            GROUP BY status
        """, {"now": now})
        for _, row in stats.iterrows():
            if row['status'] == 'NEW': new_count = int(row['cnt'])
            elif row['status'] == 'PREPARING': prep_count = int(row['cnt'])
            elif row['status'] == 'DONE': done_count = int(row['cnt'])

        avg_df = run_query("""
            SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as avg_min
            FROM kitchen_orders
            WHERE status='DONE' AND DATE(created_at) = DATE(:now) AND completed_at IS NOT NULL
        """, {"now": now})
        if not avg_df.empty and avg_df.iloc[0]['avg_min']:
            avg_time_min = int(avg_df.iloc[0]['avg_min'])
    except Exception as e:
        logger.warning(f"Kitchen stats error: {e}")

    st.markdown(f"""
    <div class="kds-header">
        <div>
            <div class="kds-title">🍳 MƏTBƏX / BARİSTA</div>
            <div style="font-size:11px; color:#888; margin-top:3px;">{now.strftime('%d.%m.%Y')}</div>
        </div>
        <div class="kds-stats">
            <div class="kds-stat">
                <div class="kds-num" style="color:#FF9800;">{new_count}</div>
                <div class="kds-label">YENİ</div>
            </div>
            <div class="kds-stat">
                <div class="kds-num" style="color:#2196F3;">{prep_count}</div>
                <div class="kds-label">HAZIRLANIR</div>
            </div>
            <div class="kds-stat">
                <div class="kds-num" style="color:#4CAF50;">{done_count}</div>
                <div class="kds-label">HAZIR</div>
            </div>
            <div class="kds-stat">
                <div class="kds-num" style="color:#9C27B0;">{avg_time_min}dəq</div>
                <div class="kds-label">ORTA VAXT</div>
            </div>
        </div>
        <div class="kds-time">{now.strftime('%H:%M')}</div>
    </div>
    """, unsafe_allow_html=True)

    col_r1, col_r2 = st.columns([3, 1])
    auto_refresh = col_r1.toggle("🔄 Avtomatik Yenilə (10 san)", value=True, key="kitchen_auto")
    if col_r2.button("🔄 İndi Yenilə", use_container_width=True, key="kitchen_manual_refresh"):
        st.rerun()

    try:
        orders = run_query("""
            SELECT * FROM kitchen_orders
            WHERE status IN ('NEW', 'PREPARING')
            AND DATE(created_at) = DATE(:now)
            ORDER BY
                CASE WHEN priority='URGENT' THEN 0 ELSE 1 END,
                CASE WHEN status='PREPARING' THEN 0 ELSE 1 END,
                created_at ASC
        """, {"now": now})
    except Exception as e:
        st.error(f"Sifarişlər yüklənərkən xəta: {e}")
        return

    if orders.empty:
        st.markdown("""
        <div style="text-align:center; padding: 80px 20px;">
            <div style="font-size: 80px; margin-bottom: 20px;">☕</div>
            <div style="font-size: 22px; font-weight: 900; color: #666;">Yeni sifariş gözlənilir...</div>
            <div style="font-size: 14px; color: #999; margin-top: 10px;">Sifarişlər avtomatik burada görünəcək</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        cols = st.columns(3)
        for idx, (_, order) in enumerate(orders.iterrows()):
            with cols[idx % 3]:
                _render_order_card(order, now)

    with st.expander(f"✅ Bu gün tamamlananlar ({done_count})", expanded=False):
        try:
            done_orders = run_query("""
                SELECT * FROM kitchen_orders
                WHERE status = 'DONE'
                AND DATE(created_at) = DATE(:now)
                ORDER BY completed_at DESC
                LIMIT 30
            """, {"now": now})

            if not done_orders.empty:
                for _, order in done_orders.iterrows():
                    try:
                        items = json.loads(order['items'])
                        items_str = ", ".join([f"{i['item_name']} ×{i['qty']}" for i in items])
                    except:
                        items_str = str(order['items'])[:60]

                    prep_time = ""
                    if order.get('completed_at') and order.get('created_at'):
                        try:
                            diff = (order['completed_at'] - order['created_at']).total_seconds() / 60
                            prep_time = f" · {int(diff)} dəq"
                        except:
                            pass

                    st.markdown(f"""
                    <div class="done-item">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:800; color:#333;">#{order['id']}</span>
                            <span style="font-size:11px; color:#888;">✅ Hazır{prep_time}</span>
                        </div>
                        <div style="font-size:13px; color:#555; margin-top:4px;">{items_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Bu gün hələ tamamlanmış sifariş yoxdur.")
        except Exception as e:
            st.warning(f"Tamamlanmış sifarişlər yüklənmədi: {e}")

    if auto_refresh:
        time.sleep(10)
        st.rerun()


def _render_order_card(order, now):
    order_id = order['id']
    status = order['status']
    priority = order.get('priority', 'NORMAL')

    elapsed_min = 0
    try:
        elapsed = now - order['created_at']
        if hasattr(elapsed, 'total_seconds'):
            elapsed_min = int(elapsed.total_seconds() / 60)
    except:
        elapsed_min = 0

    if elapsed_min < 5:
        time_css, time_text = "ko-ok", f"{elapsed_min} dəq"
    elif elapsed_min < 10:
        time_css, time_text = "ko-warn", f"⚠️ {elapsed_min} dəq"
    else:
        time_css, time_text = "ko-late", f"🔥 {elapsed_min} dəq!"

    if priority == 'URGENT':
        card_css = "ko-urgent"
    elif status == 'PREPARING':
        card_css = "ko-preparing"
    else:
        card_css = "ko-new"

    try:
        items = json.loads(order['items'])
    except:
        items = [{"item_name": str(order['items'])[:30], "qty": 1}]

    items_html = ""
    for item in items:
        items_html += f"""
        <div class="ko-item-row">
            <span class="ko-item-name">{item.get('item_name', '?')}</span>
            <span class="ko-item-qty">×{item.get('qty', 1)}</span>
        </div>
        """

    source = order.get('sale_source', 'POS')
    table_label = order.get('table_label', '')
    source_text = f"🍽️ {table_label}" if table_label else f"🏃 {source}"
    status_emoji = "🆕" if status == 'NEW' else "👨‍🍳"

    notes_html = ""
    if order.get('notes'):
        notes_html = f'<div class="ko-notes">📝 {order["notes"]}</div>'

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

    if status == 'NEW':
        c1, c2 = st.columns(2)
        if c1.button("👨‍🍳 Qəbul Et", key=f"acc_{order_id}", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET status='PREPARING', accepted_at=:t WHERE id=:id",
                {"t": now, "id": order_id}
            )
            log_system(st.session_state.get('user', 'kitchen'), "KITCHEN_ACCEPTED", {"order_id": order_id})
            st.rerun()

        if c2.button("🚨 Təcili!", key=f"urg_{order_id}", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET priority='URGENT', status='PREPARING', accepted_at=:t WHERE id=:id",
                {"t": now, "id": order_id}
            )
            log_system(st.session_state.get('user', 'kitchen'), "KITCHEN_MARKED_URGENT", {"order_id": order_id})
            st.rerun()

    elif status == 'PREPARING':
        if st.button("✅ HAZIRDIR!", key=f"done_{order_id}", type="primary", use_container_width=True):
            run_action(
                "UPDATE kitchen_orders SET status='DONE', completed_at=:t, completed_by=:u WHERE id=:id",
                {"t": now, "u": st.session_state.get('user', 'kitchen'), "id": order_id}
            )
            log_system(st.session_state.get('user', 'kitchen'), "KITCHEN_COMPLETED", {"order_id": order_id})
            st.rerun()
