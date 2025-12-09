import streamlit as st
from database import DatabaseManager
from ui_processor import render_processor
from ui_dashboard import render_dashboard
from ui_history import render_history_manager

# Configuração Principal
st.set_page_config(page_title="Divisor de Contas", layout="wide", page_icon="💰")

def main():
    st.title("💰 Finanças: Kristian & Giulia")
    
    # Cria as abas principais
    tab_proc, tab_dash, tab_hist = st.tabs(["📝 Processar Nota", "📊 Dashboard Financeiro", "🗂️ Histórico"])
    
    # Inicia o Banco de Dados (uma única vez)
    db_manager = DatabaseManager()

    # Cada aba chama sua função específica em outro arquivo
    with tab_proc:
        render_processor(db_manager)

    with tab_dash:
        render_dashboard(db_manager)

    with tab_hist:
        render_history_manager(db_manager)

    # Fecha conexão
    db_manager.close()

if __name__ == "__main__":

    main()
