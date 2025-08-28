import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
from pathlib import Path
import io
import re

# Veritabanı işlemleri
def init_db():
    try:
        conn = sqlite3.connect('linkedin_takip.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS adaylar
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      isim TEXT, tarih TEXT, aciklama TEXT,
                      davet INTEGER, randevu INTEGER, plan INTEGER,
                      kayit INTEGER, takip INTEGER, hayir INTEGER,
                      is_ariyor INTEGER)''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Veritabanı hatası: {e}")

def add_candidate(isim, tarih, aciklama, davet, randevu, plan, kayit, takip, hayir, is_ariyor):
    try:
        conn = sqlite3.connect('linkedin_takip.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT INTO adaylar (isim, tarih, aciklama, davet, randevu, plan, kayit, takip, hayir, is_ariyor)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''', 
                  (isim, tarih, aciklama, int(davet), int(randevu), int(plan), 
                   int(kayit), int(takip), int(hayir), int(is_ariyor)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Ekleme hatası: {e}")
        return False

def get_all_candidates():
    try:
        conn = sqlite3.connect('linkedin_takip.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT * FROM adaylar", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Veri okuma hatası: {e}")
        return pd.DataFrame()

def clean_column_name(col_name):
    """Excel sütun isimlerini temizleme fonksiyonu"""
    if pd.isna(col_name):
        return ""
    col_name = str(col_name).strip()
    # Yeni satır karakterlerini kaldır
    col_name = col_name.replace('\n', ' ')
    # Fazla boşlukları kaldır
    col_name = re.sub(r'\s+', ' ', col_name)
    return col_name

def import_from_excel(uploaded_file):
    try:
        # Excel dosyasını oku
        df = pd.read_excel(uploaded_file)
        
        # Sütun isimlerini temizle
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # Excel sütun isimlerini uygulama sütunlarıyla eşleştir
        column_mapping = {
            'ADI SOYADI': 'isim',
            'BAGLANTI TARIHI': 'tarih',
            'RANDEVU OLUSTU': 'randevu',
            'DAVET YAPILDI': 'davet',
            'PLAN ANLTD': 'plan',
            'YANIT': 'hayir',
            'KAYIT': 'kayit',
            'TAKIP': 'takip',
            'ACIKLAMA': 'aciklama'
        }
        
        # Sütunları yeniden adlandır
        df = df.rename(columns=column_mapping)
        
        # Eksik sütunları ekle (varsayılan değerlerle)
        expected_columns = ['isim', 'tarih', 'randevu', 'davet',  'plan', 'kayit', 'takip', 'hayir', 'is_ariyor', 'aciklama']
        for col in expected_columns:
            if col not in df.columns:
                df[col] = 0 if col in ['davet', 'randevu', 'plan', 'kayit', 'takip', 'hayir', 'is_ariyor'] else ''
        
        # Boolean değerleri dönüştür (Evet/Hayır, True/False, 1/0 vb.)
        bool_columns = ['davet', 'randevu', 'plan', 'kayit', 'takip', 'hayir', 'is_ariyor']
        for col in bool_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: 1 if str(x).lower() in ['evet', 'yes', 'true', '1', 'var', 'x', '✓'] else 0)
        
        # Tarih sütununu formatla
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce').dt.strftime('%d %m %y')
            df['tarih'] = df['tarih'].fillna('')
        
        # Veritabanına ekle
        conn = sqlite3.connect('linkedin_takip.db', check_same_thread=False)
        c = conn.cursor()
        
        for _, row in df.iterrows():
            c.execute('''INSERT INTO adaylar (isim, tarih, aciklama, davet, randevu, plan, kayit, takip, hayir, is_ariyor)
                         VALUES (?,?,?,?,?,?,?,?,?,?)''', 
                     (row.get('isim', ''), 
                      row.get('tarih', ''), 
                      row.get('is_ariyor', 0),
                      row.get('davet', 0),
                      row.get('randevu', 0),
                      row.get('plan', 0),
                      row.get('kayit', 0),
                      row.get('takip', 0),
                      row.get('hayir', 0),
                      row.get('aciklama', '')))
        
        conn.commit()
        conn.close()
        return True, "Veriler başarıyla içe aktarıldı!"
    except Exception as e:
        return False, f"İçe aktarma hatası: {e}"

def export_to_excel():
    try:
        df = get_all_candidates()
        if len(df) > 0:
            # Orijinal Excel formatına dönüştür
            column_mapping = {
                'isim': 'ADI SOYADI',
                'davet': 'DAVET YAPILDI',
                'plan': 'PLAN ANLTD',
                'kayit': 'KAYIT',
                'takip': 'TAKIP',
                'hayir': 'YANIT',
                'tarih': 'BAGLANTI TARIHI',
                'randevu': 'RANDEVU OLUSTU',
                'aciklama': 'ACIKLAMA',
                'is_ariyor': 'IS ARIYOR'
            }
            
            # Sütunları yeniden adlandır
            export_df = df.rename(columns=column_mapping)
            
            # Boolean değerleri Excel formatına dönüştür
            bool_columns = ['DAVET YAPILDI', 'PLAN ANLTD', 'KAYIT', 'TAKIP', 'YANIT', 'RANDEVU OLUSTU', 'IS ARIYOR']
            for col in bool_columns:
                if col in export_df.columns:
                    export_df[col] = export_df[col].apply(lambda x: 'EVET' if x == 1 else 'HAYIR')
            
            # Excel dosyasını bellekten indirmek için
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Adaylar')
            output.seek(0)
            
            return True, output
        else:
            return False, "Dışa aktarılacak veri bulunamadı."
    except Exception as e:
        return False, f"Dışa aktarma hatası: {e}"

# Streamlit arayüzü
def main():
    st.set_page_config(page_title="LinkedIn Takip Asistanı", layout="wide")
    st.title("📊 LinkedIn Takip Asistanı")
    
    # Veritabanını başlat
    init_db()
    
    # Sidebar - Yeni aday ekleme ve Excel işlemleri
    with st.sidebar:
        st.header("Yeni Aday Ekle")
        isim = st.text_input("İsim*", placeholder="Adayın adı soyadı")
        tarih = st.text_input("Tarih* (gg aa yy formatında)", datetime.now().strftime("%d %m %y"))
        aciklama = st.text_area("Açıklama", placeholder="Detaylı açıklama...")
        
        # Tarih doğrulama
        try:
            datetime.strptime(tarih, "%d %m %y")
            tarih_gecerli = True
        except ValueError:
            st.error("❌ Tarih formatı hatalı! Lütfen 'gg aa yy' formatında girin (örn: 15 09 23)")
            tarih_gecerli = False
        
        st.subheader("Durumlar")
        col1, col2 = st.columns(2)
        with col1:
            davet = st.checkbox("Davet Yapıldı")
            randevu = st.checkbox("Randevu Oluştu")
            plan = st.checkbox("Plan Anlatıldı")
        with col2:
            kayit = st.checkbox("Kayıt")
            takip = st.checkbox("Takip")
            hayir = st.checkbox("Hayır")
            is_ariyor = st.checkbox("İş Arıyor")
        
        if st.button("✅ Aday Ekle", type="primary"):
            if isim and tarih_gecerli:
                if add_candidate(isim, tarih, aciklama, davet, randevu, plan, kayit, takip, hayir, is_ariyor):
                    st.success("✅ Aday başarıyla eklendi!")
                    st.balloons()
                else:
                    st.error("❌ Aday eklenemedi!")
            else:
                if not isim:
                    st.warning("⚠️ Lütfen isim giriniz!")
        
        st.divider()
        st.header("Excel İşlemleri")
        
        # Excel'den içe aktarma
        uploaded_file = st.file_uploader("Excel dosyası yükleyin", type=['xlsx'])
        if uploaded_file is not None:
            if st.button("Excel'den İçe Aktar"):
                success, message = import_from_excel(uploaded_file)
                if success:
                    st.success(message)
                    st.experimental_rerun()
                else:
                    st.error(message)
        
        # Excel'e dışa aktarma
        if st.button("Excel'e Dışa Aktar"):
            success, result = export_to_excel()
            if success:
                st.download_button(
                    label="📊 Excel Dosyasını İndir",
                    data=result,
                    file_name="linkedin_adaylar.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning(result)
    
    # Ana içerik - Aday listesi
    st.header("Aday Listesi")
    df = get_all_candidates()
    
    if len(df) > 0:
        # Filtreleme
        st.subheader("Filtreleme")
        col1, col2, col3 = st.columns(3)
        with col1:
            filtre_davet = st.checkbox("Sadece Davet Yapılanlar")
            filtre_randevu = st.checkbox("Sadece Randevu Oluşanlar")
        with col2:
            filtre_plan = st.checkbox("Sadece Plan Anlatılanlar")
            filtre_kayit = st.checkbox("Sadece Kayıt Olanlar")
        with col3:
            filtre_is_ariyor = st.checkbox("Sadece İş Arayanlar")
            filtre_takip = st.checkbox("Sadece Takip Edilenler")
        
        # Filtreleme işlemi
        if filtre_davet:
            df = df[df['davet'] == 1]
        if filtre_randevu:
            df = df[df['randevu'] == 1]
        if filtre_plan:
            df = df[df['plan'] == 1]
        if filtre_kayit:
            df = df[df['kayit'] == 1]
        if filtre_is_ariyor:
            df = df[df['is_ariyor'] == 1]
        if filtre_takip:
            df = df[df['takip'] == 1]
        
        # Gösterim için DataFrame oluştur (✓ ve X için)
        display_df = df.copy()
        checkbox_columns = ['davet', 'randevu', 'plan', 'kayit', 'takip', 'hayir', 'is_ariyor']
        for col in checkbox_columns:
            display_df[col] = display_df[col].apply(lambda x: '✓' if x == 1 else '✗')
        
        # Renkli tablo gösterimi
        def color_cells(val):
            if val == '✓':
                return 'background-color: #90EE90; color: #006400; font-weight: bold;'  # Açık yeşil
            elif val == '✗':
                return 'background-color: #FFCCCB; color: #8B0000;'  # Açık kırmızı
            return ''
        
        styled_df = display_df.style.applymap(color_cells, subset=checkbox_columns)
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Silme butonu
        if st.button("🗑️ Tüm Verileri Sil"):
            try:
                conn = sqlite3.connect('linkedin_takip.db', check_same_thread=False)
                c = conn.cursor()
                c.execute("DELETE FROM adaylar")
                conn.commit()
                conn.close()
                st.success("Tüm veriler silindi!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Silme hatası: {e}")
    else:
        st.info("📝 Henüz hiç aday eklenmemiş. Sol taraftan yeni aday ekleyebilirsiniz.")
    
    # Raporlama Paneli
    st.header("📈 Raporlama Paneli")
    
    if len(df) > 0:
        total_aday = len(df)
        davet_yapilan = df['davet'].sum()
        randevu_olusan = df['randevu'].sum()
        plan_anlatilan = df['plan'].sum()
        kayit_olan = df['kayit'].sum()
        takip_edilen = df['takip'].sum()
        hayir_diyen = df['hayir'].sum()
        is_ariyor = df['is_ariyor'].sum()

        davet_randevu_oran = (randevu_olusan / davet_yapilan * 100) if davet_yapilan > 0 else 0
        plan_kayit_oran = (kayit_olan / plan_anlatilan * 100) if plan_anlatilan > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="👥 Toplam Aday", value=total_aday)
            st.metric(label="👍 Kayıt Olan", value=kayit_olan)
        with col2:
            st.metric(label="✉️ Davet Yapılan", value=davet_yapilan)
            st.metric(label="📞 Randevu Oluşan", value=randevu_olusan)
        with col3:
            st.metric(label="🗓️ Plan Anlatılan", value=plan_anlatilan)
            st.metric(label="➡️ Takip Edilen", value=takip_edilen)
        with col4:
            st.metric(label="💼 İş Arıyor", value=is_ariyor)
            st.metric(label="👎 Hayır Diyen", value=hayir_diyen)

        st.divider()
        st.subheader("Dönüşüm Oranları")
        col_oran1, col_oran2 = st.columns(2)
        with col_oran1:
            st.metric(label="Davetten Randevuya Dönüşüm Oranı", value=f"{davet_randevu_oran:.1f}%")
        with col_oran2:
            st.metric(label="Plan Anlatımından Kayıta Dönüşüm Oranı", value=f"{plan_kayit_oran:.1f}%")
    else:
        st.warning("Rapor oluşturmak için henüz veri girilmemiş.")

if __name__ == "__main__":
    main()
