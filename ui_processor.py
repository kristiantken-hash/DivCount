import streamlit as st
import pandas as pd
import os
from datetime import datetime

from parser import InvoiceParser
from core import ExpenseManager

BUFFER_DIR = "notas_pendentes"
if not os.path.exists(BUFFER_DIR):
    os.makedirs(BUFFER_DIR)

def render_processor(db_manager):
    st.markdown("### 📥 Central de Uploads")

    # --- PARTE A: UPLOAD PARA A FILA ---
    with st.expander("📤 Adicionar novas notas à fila", expanded=False):
        uploaded_files = st.file_uploader(
            "Selecione arquivos (PDF)",
            type="pdf",
            accept_multiple_files=True,
        )
        if uploaded_files:
            for f in uploaded_files:
                with open(os.path.join(BUFFER_DIR, f.name), "wb") as buffer:
                    buffer.write(f.getbuffer())
            st.success(f"{len(uploaded_files)} notas enviadas para a fila!")
            st.rerun()

    # --- PARTE B: SELECIONAR DA FILA ---
    pendentes = [f for f in os.listdir(BUFFER_DIR) if f.lower().endswith(".pdf")]

    if not pendentes:
        st.info("🎉 Fila vazia! Nenhuma nota pendente.")
        return

    st.markdown(f"#### 📋 Fila: {len(pendentes)} notas aguardando")
    arquivo_selecionado = st.selectbox("Nota atual:", pendentes, index=0)
    current_file_path = os.path.join(BUFFER_DIR, arquivo_selecionado)

    # --- PARTE C: PROCESSAMENTO ---
    parser = InvoiceParser(current_file_path)
    core_manager = ExpenseManager()

    try:
        data = parser.parse()
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        if st.button("🗑️ Deletar arquivo corrompido"):
            os.remove(current_file_path)
            st.rerun()
        return

    st.markdown("---")

    # Metadados (Data, Loja, Pagador)
    c1, c2, c3, c4 = st.columns(4)

    data_padrao = datetime.today()
    if data.get("data"):
        try:
            data_padrao = datetime.strptime(data["data"], "%d/%m/%Y")
        except:
            pass

    nova_data = c1.date_input(
        "Data da Nota",
        value=data_padrao,
        format="DD/MM/YYYY",
    )
    data_formatada_str = nova_data.strftime("%d/%m/%Y")

    c2.info(f"🛒 {data.get('loja', 'Loja não identificada')}")
    c3.info(f"💳 {data.get('forma_pagamento', 'Indefinido')}")

    opcoes_pagador = ["Kristian", "Giulia", "Outro"]
    sugestao = core_manager.identify_payer(data.get("cpf_consumidor"))
    idx_pagador = opcoes_pagador.index(sugestao) if sugestao in opcoes_pagador else 2
    pagador_final = c4.selectbox("Quem pagou?", opcoes_pagador, index=idx_pagador)

    st.markdown("### 📝 Classificar Itens")

    itens_raw = data.get("itens", [])
df_itens = pd.DataFrame(itens_raw)

if df_itens.empty:
    st.warning("Nenhum item identificado na nota.")
    return

# ---- NOVO: função que usa memória + fallback ----
def sugerir_categoria(nome_item: str) -> str:
    if not nome_item:
        return "Geral"

    # 1) Tenta memória no banco
    learned = db_manager.get_learned_category(nome_item)
    if learned:
        return learned

    # 2) Se não tiver memória, usa o palpite padrão
    return core_manager.categorize_item(nome_item)

# Usa a função acima para preencher a coluna Categoria
df_itens["Categoria"] = df_itens["item"].apply(
    lambda nome: sugerir_categoria(str(nome))
)
    # --- FORM de edição + salvamento ---
    with st.form("form_editar_nota"):
        # Cabeçalho visual
        c_h1, c_h2, c_h3, c_h4 = st.columns([5, 1, 1.5, 1.5])
        c_h1.markdown("**Item**")
        c_h2.markdown("**Qtd**")
        c_h3.markdown("**Valor (R$)**")
        c_h4.markdown("**Categoria**")

        itens_processados = []
        total_nota = 0.0

        for idx, row in df_itens.iterrows():
            c1, c2, c3, c4 = st.columns([5, 1, 1.5, 1.5])

            nome_item = c1.text_input(
                "Nome",
                value=str(row["item"]),
                key=f"nome_{idx}",
                label_visibility="collapsed",
            )
            qtd_item = c2.number_input(
                "Qtd",
                value=float(row.get("qtd", 1.0) or 1.0),
                min_value=0.0,
                step=0.1,
                key=f"qtd_{idx}",
                label_visibility="collapsed",
            )
            valor_item = c3.number_input(
                "Valor (R$)",
                value=float(row.get("valor", 0.0) or 0.0),
                min_value=0.0,
                step=0.1,
                key=f"valor_{idx}",
                label_visibility="collapsed",
            )

            # Sugestão de categoria
            categorias_opcoes = [
                "Hortifruti", "Carnes", "Bebidas",
                "Padaria", "Limpeza", "Higiene", "Geral",
            ]
            cat_sugerida = row["Categoria"] if row.get("Categoria") else "Geral"
            idx_cat = categorias_opcoes.index(cat_sugerida) if cat_sugerida in categorias_opcoes else len(categorias_opcoes) - 1
            
            categoria_escolhida = c4.selectbox(
                "Categoria",
                categorias_opcoes,
                index=idx_cat,
                key=f"cat_{idx}",
                label_visibility="collapsed",
            )


            total_nota += valor_item

            # Aqui você poderia dividir entre Kristian e Giulia (regra que já tiver)
            # Exemplo simples: 50/50
            valor_k = round(valor_item / 2.0, 2)
            valor_g = round(valor_item - valor_k, 2)

            itens_processados.append(
                {
                    "Item": nome_item,
                    "Valor (R$)": valor_item,
                    "Categoria": categoria_escolhida,
                    "R$ Kristian": valor_k,
                    "R$ Giulia": valor_g,
                }
            )

        # --- Resumo da nota ---
        st.markdown("---")
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("Total da Nota", f"R$ {total_nota:.2f}")
        col_res2.metric("Qtd de Itens", len(itens_processados))
        col_res3.metric("Pagador", pagador_final)

        salvar = st.form_submit_button("💾 Salvar nota e remover da fila")

    # --- Pós-submit ---
    if salvar:
        sucesso = db_manager.save_invoice(
            data_formatada_str,
            data.get("loja", "Loja não identificada"),
            total_nota,
            pagador_final,
            data.get("forma_pagamento", "Indefinido"),
            itens_processados,
        )

        if sucesso:
            # Aprendizado: salva categorias escolhidas na memória
            for item in itens_processados:
                db_manager.learn_item(item["Item"], item["Categoria"])

            st.toast("Nota salva com sucesso!", icon="✅")

            # Remove o PDF da fila após salvar
            os.remove(current_file_path)
            st.rerun()
        else:
            st.error("Erro ao salvar nota. Tente novamente.")


