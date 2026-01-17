# --- CSS DİZAYN (TAM GİZLİLİK - YENİLƏNMİŞ) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500&display=swap');

    /* === GİZLƏTMƏ KODLARI (Aqressiv) === */
    
    /* 1. Yuxarıdakı Header (Fork, Menu, GitHub) */
    header[data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 2. Yuxarı sağdakı rəngli xətt (Decoration) */
    div[data-testid="stDecoration"] {
        display: none !important;
    }

    /* 3. Aşağıdakı Footer (Made with Streamlit) */
    footer {
        display: none !important;
        visibility: hidden !important;
    }

    /* 4. Aşağı Sağdakı Toolbar (Qırmızı Tac, Deploy, Running Man) */
    div[data-testid="stToolbar"] {
        display: none !important;
        visibility: hidden !important;
    }
    div[class*="stAppDeployButton"] {
        display: none !important;
    }
    div[data-testid="stStatusWidget"] {
        display: none !important;
    }
    
    /* Main Menu (Üç nöqtə) */
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }

    /* === DİZAYN TƏNZİMLƏMƏLƏRİ === */

    /* Mobil üçün boşluqlar (Header gizləndiyi üçün yuxarını sıxırıq) */
    .block-container {
        padding-top: 1rem !important; 
        padding-bottom: 1rem !important;
    }
    
    .stApp { background-color: #ffffff; }

    /* Fontlar */
    h1, h2, h3 { font-family: 'Anton', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
    p, div { font-family: 'Oswald', sans-serif; }

    /* Logo Mərkəzləşdirmə */
    [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }

    /* Kofe Grid Sistemi */
    .coffee-grid {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-bottom: 5px;
        margin-top: 5px;
    }
    
    .coffee-item {
        width: 17%; 
        max-width: 50px;
        transition: transform 0.2s ease;
    }
    
    .coffee-item.active { transform: scale(1.1); filter: drop-shadow(0px 3px 5px rgba(0,0,0,0.2)); }

    /* Yaşıl Mesaj Qutusu */
    .promo-box {
        background-color: #2e7d32;
        color: white;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-top: 15px;
        box-shadow: 0 4px 8px rgba(46, 125, 50, 0.25);
        border: 1px solid #1b5e20;
    }
    
    /* Qalan Sayğac Mətni (Qırmızı) */
    .counter-text {
        text-align: center;
        font-size: 19px;
        font-weight: 500;
        color: #d32f2f;
        margin-top: 8px;
    }
    
    /* Input Sahəsi (Barista) */
    .stTextInput input { text-align: center; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)
