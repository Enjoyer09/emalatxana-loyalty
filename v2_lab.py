import streamlit as st
import psycopg2
import pandas as pd
import os

# 1. DB Qosulmasi
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        return conn
    except Exception as e:
        st.error(f"DB Xətası: {e}")
        return None

st.set_page_config(page_title="Ironwaves V2 Lab", layout="wide")
st.title("🧪 V2 Laboratoriyası: Anbar və Maya Dəyəri")

# Naviqasiya
tab1, tab2, tab3 = st.tabs(["📦 Anbar (Inventory)", "📜 Reseptlər", "💰 Maya Dəyəri Analizi"])

conn = get_db_connection()

# --- TAB 1: ANBAR İDARƏETMƏSİ ---
with tab1:
    st.header("Xammal Siyahısı")
    
    # Yeni mal əlavə etmə forması
    with st.expander("Yeni Xammal Əlavə Et"):
        with st.form("add_inventory"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Ad (məs: Süd, Kofe dənəsi)")
            unit = col2.selectbox("Ölçü vahidi", ["kq", "litr", "ədəd", "qr"])
            stock = col1.number_input("Stok miqdarı", min_value=0.0, step=0.1)
            cost = col2.number_input("Vahid qiyməti (AZN)", min_value=0.0, step=0.01)
            alert = st.number_input("Xəbərdarlıq limiti", min_value=0.0, step=1.0)
            
            submitted = st.form_submit_button("Əlavə et")
            if submitted and conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO inventory (name, unit, stock_level, cost_per_unit, alert_limit)
                    VALUES (%s, %s, %s, %s, %s)
                """, (name, unit, stock, cost, alert))
                conn.commit()
                cur.close()
                st.success(f"{name} əlavə edildi!")
                st.rerun()

    # Cədvəli göstər
    if conn:
        df_inv = pd.read_sql("SELECT * FROM inventory ORDER BY id", conn)
        st.dataframe(df_inv, use_container_width=True)

# --- TAB 2: RESEPTLƏRİN QURULMASI ---
with tab2:
    st.header("Məhsul Reseptləri")
    st.info("Burada menyu məhsullarını anbar məhsulları ilə əlaqələndiririk.")
    
    if conn:
        # Menyu və Anbar siyahısını alırıq (Qeyd: menu_items cədvəli V1-də varsa)
        # Hələlik sadəlik üçün inventory-dən çəkirik
        inv_items = pd.read_sql("SELECT id, name, unit FROM inventory", conn)
        
        # Resept yaratma Formu
        with st.form("add_recipe"):
            # Real layihədə bu hissə menu_items cədvəlindən gəlməlidir
            menu_item_id = st.number_input("Menu Item ID (V1-dən)", min_value=1, step=1)
            item_name_cached = st.text_input("Məhsul Adı (məs: Latte)")
            
            # Hansı xammaldan istifadə olunur?
            ingredient = st.selectbox("Xammal seçin", inv_items['name'].tolist())
            qty = st.number_input("İstifadə miqdarı", min_value=0.0, step=0.001, format="%.3f")
            
            submitted_recipe = st.form_submit_button("Reseptə Əlavə Et")
            
            if submitted_recipe:
                inv_id = int(inv_items[inv_items['name'] == ingredient]['id'].values[0])
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO recipes (menu_item_id, item_name_cached, inventory_item_id, quantity_required)
                    VALUES (%s, %s, %s, %s)
                """, (menu_item_id, item_name_cached, inv_id, qty))
                conn.commit()
                cur.close()
                st.success("Resept komponenti əlavə edildi!")

        # Mövcud reseptləri göstər
        st.subheader("Mövcud Reseptlər")
        sql_recipes = """
            SELECT r.id, r.item_name_cached, i.name as xammal, r.quantity_required, i.unit 
            FROM recipes r
            JOIN inventory i ON r.inventory_item_id = i.id
        """
        df_recipes = pd.read_sql(sql_recipes, conn)
        st.dataframe(df_recipes)

# --- TAB 3: AVTOMATİK MAYA DƏYƏRİ ---
with tab3:
    st.header("Maya Dəyəri Hesablanması (Real-time)")
    
    if conn and not df_recipes.empty:
        # Hər bir menyu məhsulu üçün maya dəyərini hesablayırıq
        # Formula: (Tələb olunan miqdar * Vahid qiyməti)
        sql_cost = """
            SELECT 
                r.item_name_cached as mehsul,
                SUM(r.quantity_required * i.cost_per_unit) as maya_deyeri
            FROM recipes r
            JOIN inventory i ON r.inventory_item_id = i.id
            GROUP BY r.item_name_cached
        """
        df_cost = pd.read_sql(sql_cost, conn)
        st.dataframe(df_cost)
        
        st.bar_chart(df_cost.set_index("mehsul"))

if conn:
    conn.close()
