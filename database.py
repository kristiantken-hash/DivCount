import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit as st
from datetime import datetime

# Não usamos mais arquivo local, usamos a URL da nuvem
# A URL deve estar configurada no secrets.toml (local) ou nos Secrets do Streamlit Cloud

class DatabaseManager:
    def __init__(self):
        try:
            # Busca a conexão nos segredos do Streamlit
            # Formato esperado no secrets:
            # [connections.postgresql]
            # dialect = "postgresql"
            # host = "..."
            # port = "..."
            # database = "..."
            # username = "..."
            # password = "..."
            # OU simplesmente uma string de conexão direta chamada DATABASE_URL
            
            # Opção A: Usando st.connection (Mais moderno no Streamlit)
            # self.conn = st.connection("postgresql", type="sql").session 
            # Mas para manter compatibilidade com seu código atual, vamos usar psycopg2 direto:
            
            db_url = st.secrets["DATABASE_URL"]
            self.conn = psycopg2.connect(db_url)
            self.conn.autocommit = False # Controle manual de transação igual fazíamos antes
            self._create_tables()
            
        except Exception as e:
            st.error(f"Erro ao conectar no Banco de Dados: {e}")
            st.stop()

    def _get_cursor(self):
        # RealDictCursor faz o Postgres devolver dicionários igual o pandas gosta
        return self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def _create_tables(self):
        cur = self.conn.cursor()
        
        # Tabela Notas (SERIAL é o autoincrement do Postgres)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id SERIAL PRIMARY KEY,
                data_compra TEXT NOT NULL,
                loja TEXT NOT NULL,
                total_nota REAL NOT NULL,
                pagador TEXT NOT NULL,
                forma_pagamento TEXT, 
                data_registro TEXT NOT NULL
            );
        """)
        
        # Tabela Itens
        cur.execute("""
            CREATE TABLE IF NOT EXISTS itens (
                id SERIAL PRIMARY KEY,
                nota_id INTEGER NOT NULL,
                item_nome TEXT NOT NULL,
                valor REAL NOT NULL,
                categoria TEXT NOT NULL,
                kristian_parte REAL NOT NULL,
                giulia_parte REAL NOT NULL,
                FOREIGN KEY (nota_id) REFERENCES notas(id) ON DELETE CASCADE
            );
        """)
        
        # Tabela Reembolsos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reembolsos (
                id SERIAL PRIMARY KEY,
                data_pagamento TEXT NOT NULL,
                pagador TEXT NOT NULL,
                recebedor TEXT NOT NULL,
                valor REAL NOT NULL,
                comprovante TEXT,
                data_registro TEXT NOT NULL
            );
        """)
        
        # Tabela Memória (Aprendizado)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memoria_itens (
                item_nome TEXT PRIMARY KEY,
                categoria TEXT NOT NULL,
                ultima_atualizacao TEXT
            );
        """)
        
        self.conn.commit()
        cur.close()

    # --- FUNÇÕES DE APRENDIZADO ---
    def get_learned_category(self, item_nome):
        cur = self.conn.cursor()
        cur.execute("SELECT categoria FROM memoria_itens WHERE item_nome = %s", (item_nome,))
        result = cur.fetchone()
        cur.close()
        return result[0] if result else None

    def learn_item(self, item_nome, categoria):
        data_hoje = datetime.now().date()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO memoria_itens (item_nome, categoria, ultima_atualizacao)
            VALUES (%s, %s, %s)
            ON CONFLICT (item_nome)
            DO UPDATE SET categoria = EXCLUDED.categoria,
                          ultima_atualizacao = EXCLUDED.ultima_atualizacao;
            """,
            (item_nome, categoria, data_hoje),
        )
        self.conn.commit()
        cur.close()


    # --- SALVAR NOTA ---
    def save_invoice(self, data_nota, loja, total_nota, pagador, forma_pagamento, itens_processados):
        # data_nota vem como string "dd/mm/YYYY" da UI: converte para date
        data_compra_date = datetime.strptime(data_nota, "%d/%m/%Y").date()
        data_registro = datetime.now()  # datetime completo
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO notas (data_compra, loja, total_nota, pagador, forma_pagamento, data_registro)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                """,
                (data_compra_date, loja, total_nota, pagador, forma_pagamento, data_registro),
            )
            
            nota_id = cur.fetchone()[0] # Pega o ID gerado

            item_list = []
            for item in itens_processados:
                # Salva na lista para insert em lote
                item_list.append((nota_id, item['Item'], item['Valor (R$)'], item['Categoria'], item['R$ Kristian'], item['R$ Giulia']))
                
                # Ensina o robô (um por um pois é rápido)
                self.learn_item(item['Item'], item['Categoria'])

            # Insert em lote no Postgres
            args_str = ','.join(cur.mogrify("(%s,%s,%s,%s,%s,%s)", x).decode('utf-8') for x in item_list)
            cur.execute("INSERT INTO itens (nota_id, item_nome, valor, categoria, kristian_parte, giulia_parte) VALUES " + args_str)
            
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.conn.rollback()
            cur.close()
            print(f"Erro SQL: {e}")
            return False

    # --- SALVAR REEMBOLSO ---
    def save_reimbursement(self, pagador, recebedor, valor):
        data_hoje = datetime.now().date()
        data_registro = datetime.now()
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO reembolsos (data_pagamento, pagador, recebedor, valor, data_registro)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (data_hoje, pagador, recebedor, valor, data_registro),
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            self.conn.rollback()
            cur.close()
            return False

    # --- LEITURA DE DADOS ---
    def get_financial_data(self):
        query_notas = """
            SELECT n.id as nota_id, n.data_compra, n.loja, n.pagador, n.forma_pagamento,
                i.item_nome, i.categoria, i.valor, i.kristian_parte, i.giulia_parte
            FROM notas n JOIN itens i ON n.id = i.nota_id
        """
        # Pandas lê direto do Postgres se tiver a conexão
        df_compras = pd.read_sql_query(query_notas, self.conn)
        df_reembolsos = pd.read_sql_query("SELECT * FROM reembolsos", self.conn)
        return df_compras, df_reembolsos
    
    def get_all_invoices(self):
        cur = self._get_cursor() # Usa cursor de dicionário
        cur.execute("SELECT id, data_compra, loja, total_nota, pagador FROM notas ORDER BY data_compra DESC")
        res = cur.fetchall()
        cur.close()
        # Converte para lista de dicts puros se necessário, mas RealDictCursor já ajuda
        return [dict(row) for row in res]

    def get_all_reimbursements(self):
        cur = self._get_cursor()
        cur.execute("SELECT id, data_pagamento, pagador, recebedor, valor FROM reembolsos ORDER BY data_pagamento DESC")
        res = cur.fetchall()
        cur.close()
        return [dict(row) for row in res]

    # --- DELETAR ---
    def delete_invoice(self, note_id):
        cur = self.conn.cursor()
        try:
            # No Postgres, se configurarmos ON DELETE CASCADE na chave estrangeira,
            # apagar a nota apaga os itens automaticamente. Mas vamos garantir:
            cur.execute("DELETE FROM itens WHERE nota_id = %s", (note_id,))
            cur.execute("DELETE FROM notas WHERE id = %s", (note_id,))
            self.conn.commit()
            cur.close()
            return True
        except:
            self.conn.rollback()
            cur.close()
            return False

    def delete_reimbursement(self, reimb_id):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM reembolsos WHERE id = %s", (reimb_id,))
            self.conn.commit()
            cur.close()
            return True
        except:
            self.conn.rollback()
            cur.close()
            return False

    def close(self):

        self.conn.close()
