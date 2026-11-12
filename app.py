import streamlit as st
import pandas as pd
import base64
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

st.set_page_config(page_title="Gestão Bem Pensado", page_icon="🧁", layout="wide")
# Limpeza visual: esconde cabeçalho, rodapé e menu padrão do Streamlit
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Ajuste fino para o fundo da página e do menu lateral */
    [data-testid="stAppViewContainer"] { background-color: #FDFBF7; }
    [data-testid="stSidebar"] { background-color: #F5EBE6; }
    </style>
    """, unsafe_allow_html=True)

# Exibe a logo do Bem Pensado no topo do menu lateral
try:
    st.sidebar.image("logo.png", use_container_width=True)
    st.sidebar.markdown("---")
except:
    pass # Caso a imagem ainda não tenha carregado, o sistema não trava

# Conexão segura com sistema Anti-Falhas

def init_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except Exception as e:
        st.error("🚨 **ALERTA: Falha na Conexão com o Banco de Dados**")
        st.info("Verifique a variável `DB_URL` no Streamlit Secrets.")
        st.code(str(e))
        st.stop()

conn = init_connection()

# Função para garantir que as tabelas existam
def create_tables():
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insumos (
            id SERIAL PRIMARY KEY, nome TEXT UNIQUE NOT NULL, unidade TEXT NOT NULL,
            preco_compra NUMERIC NOT NULL, peso_bruto NUMERIC NOT NULL, peso_liquido NUMERIC NOT NULL,
            fator_correcao NUMERIC NOT NULL, custo_real_unitario NUMERIC NOT NULL,
            estoque_atual NUMERIC DEFAULT 0, estoque_minimo NUMERIC DEFAULT 0
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS custos_fixos (id SERIAL PRIMARY KEY, nome TEXT UNIQUE NOT NULL, valor_mensal NUMERIC NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS config_negocio (id SERIAL PRIMARY KEY, horas_trabalhadas_mes NUMERIC DEFAULT 160, dias_trabalhados_mes NUMERIC DEFAULT 22)")
    cursor.execute("INSERT INTO config_negocio (id, horas_trabalhadas_mes, dias_trabalhados_mes) VALUES (1, 160, 22) ON CONFLICT (id) DO NOTHING")
    cursor.execute("CREATE TABLE IF NOT EXISTS taxas_pagamento (id SERIAL PRIMARY KEY, nome TEXT UNIQUE NOT NULL, taxa_percentual NUMERIC NOT NULL, prazo_recebimento_dias INTEGER DEFAULT 1)")
    cursor.execute("CREATE TABLE IF NOT EXISTS receitas (id SERIAL PRIMARY KEY, nome TEXT UNIQUE NOT NULL, rendimento NUMERIC NOT NULL, tempo_preparo_minutos NUMERIC NOT NULL, modo_preparo TEXT, imagem_base64 TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS receita_itens (id SERIAL PRIMARY KEY, receita_id INTEGER NOT NULL REFERENCES receitas(id) ON DELETE CASCADE, insumo_id INTEGER NOT NULL REFERENCES insumos(id), quantidade NUMERIC NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS fluxo_caixa (id SERIAL PRIMARY KEY, data TEXT NOT NULL, tipo TEXT NOT NULL, categoria TEXT NOT NULL, descricao TEXT, valor NUMERIC NOT NULL)")
    conn.commit()

create_tables()

# --- MENU ---
menu = st.sidebar.radio("Navegação", ["🏠 Início", "📦 Insumos", "🛒 Estoque & Compras", "🏢 Custos Fixos", "📋 Fichas Técnicas", "💲 Precificação Inteligente", "💸 Fluxo de Caixa", "📊 Ponto de Equilíbrio & DRE"], label_visibility="collapsed")

# --- ÁREA DE SEGURANÇA E BACKUP ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Segurança")

if st.sidebar.button("💾 Gerar Backup Completo", use_container_width=True):
    with st.spinner("Empacotando todo o sistema..."):
        try:
            import io
            
            # Busca o nome de todas as tabelas que existem no seu banco de dados
            query_tabelas = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            df_tabelas = pd.read_sql(query_tabelas, conn)
            
            # Cria o arquivo Excel na memória
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Roda por todas as tabelas e cria uma aba para cada uma
                for tabela in df_tabelas['table_name']:
                    df_temp = pd.read_sql(f"SELECT * FROM {tabela}", conn)
                    nome_aba = tabela[:31] 
                    df_temp.to_excel(writer, index=False, sheet_name=nome_aba)
            
            # Exibe o botão final para baixar o arquivo
            st.sidebar.download_button(
                label="📥 Baixar Excel com Tudo",
                data=output.getvalue(),
                file_name="Backup_Completo_Bem_Pensado.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True,
                type="primary"
            )
        except Exception as e:
            st.sidebar.error(f"Erro ao gerar backup: {e}")

if menu == "🏠 Início":
    st.title("🧁 Sistema de Gestão Bem Pensado")
    st.write("Bem-vinda ao seu centro de controle! Selecione uma opção no menu lateral para gerir as suas receitas e custos.")# Funções auxiliares
def run_query(query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        conn.commit()

def fetch_data(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

# --- MÓDULOS ---

if menu == "📦 Insumos":
    st.header("Cadastro de Insumos & Fator de Correção")
    
    # Mágica silenciosa: adiciona a coluna "marca" no banco de dados se ela não existir
    try:
        run_query("ALTER TABLE insumos ADD COLUMN IF NOT EXISTS marca TEXT DEFAULT '-';")
    except:
        pass

    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("form_insumo", clear_on_submit=True):
            f_col1, f_col2 = st.columns(2)
            
            with f_col1:
                nome = st.text_input("Nome do Insumo")
                marca = st.text_input("Marca (Ex: Italac, Moça)")
                preco = st.number_input("Preço Pago (R$)", min_value=0.01)
                peso_liquido = st.number_input("Qtd Real Aproveitada (g, ml, un)", min_value=0.01)
                
            with f_col2:
                unidade = st.selectbox("Unidade de Uso", ["g", "ml", "unid"])
                peso_bruto = st.number_input("Qtd Total Comprada (g, ml, un)", min_value=0.01)
                est_atual = st.number_input("Estoque Atual", min_value=0.0)
            
            if st.form_submit_button("Cadastrar Insumo"):
                fc = peso_bruto / peso_liquido
                custo_real = (preco / peso_bruto) * fc
                
                query = "INSERT INTO insumos (nome, marca, unidade, preco_compra, peso_bruto, peso_liquido, fator_correcao, custo_real_unitario, estoque_atual) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                run_query(query, (nome, marca, unidade, preco, peso_bruto, peso_liquido, fc, custo_real, est_atual))
                
                st.success("Salvo com sucesso!")
                st.rerun()

    with col2:
        # Puxa os dados incluindo o preço para exibir na tabela
        df_ins = fetch_data("SELECT id, nome, marca, preco_compra, custo_real_unitario FROM insumos ORDER BY nome")
        
        if not df_ins.empty:
            # Lista de pesquisa mostrando APENAS o nome do insumo
            pesquisa = st.selectbox(
                "🔍 Buscar Insumo na Tabela:", 
                df_ins['nome'].tolist(),
                index=None,
                placeholder="Pesquisar insumo..."
            )
            
            # Filtra a tabela
            if pesquisa:
                df_filtrado = df_ins[df_ins['nome'] == pesquisa]
            else:
                df_filtrado = df_ins
                
            # Exibe a tabela configurada com o Preço Pago aparecendo apenas aqui
            st.dataframe(
                df_filtrado, 
                column_config={
                    "id": None, # Esconde o ID para ficar mais limpo
                    "nome": "Insumo",
                    "marca": "Marca",
                    "preco_compra": st.column_config.NumberColumn("Preço Pago (R$)", format="R$ %.2f"),
                    "custo_real_unitario": st.column_config.NumberColumn("Custo Unitário (R$)", format="R$ %.4f")
                },
                hide_index=True, 
                use_container_width=True
            )
        else:
            st.info("Nenhum insumo cadastrado ainda.")

    # --- NOVA ÁREA: EDITAR E EXCLUIR ---
    st.markdown("---")
    st.subheader("✏️ Atualizar ou Excluir Insumos")
    st.info("💡 Se você atualizar o preço aqui, TODAS as Fichas Técnicas que usam este ingrediente serão recalculadas automaticamente!")

    # Adicionado o 'estoque_atual' na busca do banco de dados
    df_edit = fetch_data("SELECT id, nome, preco_compra, peso_bruto, peso_liquido, marca, estoque_atual FROM insumos ORDER BY nome")
    
    if not df_edit.empty:
        opcoes = [""] + df_edit.apply(lambda row: f"{row['id']} - {row['nome']} ({row['marca']})", axis=1).tolist()
        selecao = st.selectbox("Selecione o Insumo:", opcoes)
        
        if selecao != "":
            insumo_id = int(selecao.split(" - ")[0])
            dados_atuais = df_edit[df_edit['id'] == insumo_id].iloc[0]
            
            with st.form("form_editar"):
                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    novo_preco = st.number_input("Novo Preço Pago (R$)", value=float(dados_atuais['preco_compra']), min_value=0.01)
                    novo_pb = st.number_input("Novo Peso Total Comprado", value=float(dados_atuais['peso_bruto']), min_value=0.01)
                with e_col2:
                    novo_pl = st.number_input("Novo Peso Real Aproveitado", value=float(dados_atuais['peso_liquido']), min_value=0.01)
                    # Novo campo para editar o estoque atual
                    estoque_bd = dados_atuais['estoque_atual']
                    novo_estoque = st.number_input("Novo Estoque Atual", value=float(estoque_bd) if pd.notna(estoque_bd) else 0.0, min_value=0.0)
                    
                st.markdown("---")
                btn1, btn2 = st.columns(2)
                with btn1:
                    if st.form_submit_button("💾 Salvar Alterações"):
                        novo_fc = novo_pb / novo_pl
                        novo_custo = (novo_preco / novo_pb) * novo_fc
                        
                        # A query de atualização agora inclui o estoque_atual
                        query_upd = "UPDATE insumos SET preco_compra=%s, peso_bruto=%s, peso_liquido=%s, fator_correcao=%s, custo_real_unitario=%s, estoque_atual=%s WHERE id=%s"
                        run_query(query_upd, (novo_preco, novo_pb, novo_pl, novo_fc, novo_custo, novo_estoque, insumo_id))
                        st.success("Atualizado com sucesso!")
                        st.rerun()
                with btn2:
                    if st.form_submit_button("🗑️ Excluir Insumo Permanentemente"):
                        run_query("DELETE FROM insumos WHERE id=%s", (insumo_id,))
                        st.success("Insumo excluído!")
                        st.rerun()
if menu == "🏢 Custos Fixos":
    st.header("Gestão de Custos Fixos")
    
    try:
        df_cf = pd.read_sql("SELECT id, nome, valor_mensal FROM custos_fixos ORDER BY nome", conn)
    except:
        try:
            conn.rollback()
        except:
            pass
        df_cf = pd.DataFrame()

    if not df_cf.empty and 'valor_mensal' in df_cf.columns:
        st.metric("Total Custos Fixos", f"R$ {df_cf['valor_mensal'].sum():.2f}")
        
        st.subheader("📋 Custos Cadastrados")
        st.dataframe(
            df_cf[['nome', 'valor_mensal']], 
            column_config={
                "nome": "Custo Fixo",
                "valor_mensal": st.column_config.NumberColumn("Valor Mensal (R$)", format="R$ %.2f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.metric("Total Custos Fixos", "R$ 0.00")
        st.info("Nenhum custo fixo cadastrado ainda.")

    # --- NOVA ÁREA: EDITAR CUSTO FIXO ---
    st.markdown("---")
    st.subheader("✏️ Atualizar ou Excluir Custo Fixo")

    if not df_cf.empty:
        opcoes_cf = [""] + df_cf.apply(lambda row: f"{row['id']} - {row['nome']} (R$ {row['valor_mensal']:.2f})", axis=1).tolist()
        selecao_cf = st.selectbox("Selecione o Custo para Editar ou Excluir:", opcoes_cf)
        
        if selecao_cf != "":
            cf_id = int(selecao_cf.split(" - ")[0])
            dados_cf = df_cf[df_cf['id'] == cf_id].iloc[0]
            
            with st.form("form_editar_cf"):
                novo_nome_cf = st.text_input("Nome do Custo", value=str(dados_cf['nome']))
                novo_valor_cf = st.number_input("Novo Valor Mensal (R$)", value=float(dados_cf['valor_mensal']), min_value=0.01)
                
                st.markdown("---")
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.form_submit_button("💾 Salvar Alterações"):
                        try:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE custos_fixos SET nome=%s, valor_mensal=%s WHERE id=%s", (novo_nome_cf, novo_valor_cf, cf_id))
                            conn.commit()
                            st.success("Custo fixo atualizado com sucesso!")
                            st.rerun()
                        except Exception as ex:
                            try:
                                conn.rollback()
                            except:
                                pass
                            st.error(f"Erro ao atualizar: {ex}")
                with b_col2:
                    if st.form_submit_button("🗑️ Excluir Permanentemente"):
                        try:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM custos_fixos WHERE id=%s", (cf_id,))
                            conn.commit()
                            st.success("Custo fixo excluído!")
                            st.rerun()
                        except Exception as ex:
                            try:
                                conn.rollback()
                            except:
                                pass
                            st.error(f"Erro ao excluir: {ex}")
    else:
        st.info("Não há custos disponíveis para edição.")

if menu == "📋 Fichas Técnicas":
    # Criamos colunas para colocar o botão de limpar ao lado do título
    col_tit1, col_tit2 = st.columns([3, 1])
    with col_tit1:
        st.header("Montagem das Fichas Técnicas")
    with col_tit2:
        st.write("") # Pequeno espaço para alinhar com o título
        def limpar_dados():
            st.session_state["input_nome_receita_unico"] = ""
            st.session_state["input_rendimento_unico"] = 1.0
            st.session_state["input_peso_total_unico"] = 1000.0
            st.session_state.itens_receita = []
        
        st.button("✨ Nova Receita / Limpar", on_click=limpar_dados, use_container_width=True, key="btn_limpar_receita_topo")
           
    # 1. Tenta criar as tabelas caso não existam (o código continua igual daqui para baixo...)
    
    # 1. Tenta criar as tabelas caso não existam
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receitas (
                id SERIAL PRIMARY KEY,
                nome TEXT UNIQUE,
                rendimento_unidades NUMERIC,
                peso_total_g NUMERIC
            );
            CREATE TABLE IF NOT EXISTS receita_itens (
                id SERIAL PRIMARY KEY,
                receita_id INTEGER REFERENCES receitas(id) ON DELETE CASCADE,
                insumo_id INTEGER REFERENCES insumos(id),
                quantidade_usada NUMERIC
            );
        """)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except:
            pass

    # 2. Força a adição das colunas novas e limpa as antigas que estão a bloquear o sistema
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE receitas ADD COLUMN rendimento_unidades NUMERIC DEFAULT 1.0;")
        conn.commit()
    except:
        conn.rollback()
        
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE receitas ADD COLUMN peso_total_g NUMERIC DEFAULT 1000.0;")
        conn.commit()
    except:
        conn.rollback()

    # Força a adição da coluna nova na tabela de itens
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE receita_itens ADD COLUMN quantidade_usada NUMERIC DEFAULT 0;")
        conn.commit()
    except:
        conn.rollback()

    # Remove as colunas antigas para limpar a tabela e parar os erros
    try:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE receitas DROP COLUMN IF EXISTS rendimento CASCADE;")
        cursor.execute("ALTER TABLE receitas DROP COLUMN IF EXISTS peso_total CASCADE;")
        cursor.execute("ALTER TABLE receitas DROP COLUMN IF EXISTS custo_total CASCADE;")
        cursor.execute("ALTER TABLE receitas DROP COLUMN IF EXISTS tempo_preparo_minutos CASCADE;")
        # A linha nova que vai limpar a tabela de ingredientes:
        cursor.execute("ALTER TABLE receita_itens DROP COLUMN IF EXISTS quantidade CASCADE;")
        conn.commit()
    except:
        conn.rollback()

    # Continuação normal...
    nome_receita = st.text_input("Nome da Receita / Produto (Ex: Brownie Tradicional)", key="input_nome_receita_unico")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        rendimento = st.number_input("Rendimento (Quantas unidades ou porções rende?)", min_value=1.0, value=1.0, key="input_rendimento_unico")
    with col_r2:
        peso_total = st.number_input("Peso Total Final da Receita (em gramas ou ml)", min_value=0.1, value=1000.0, key="input_peso_total_unico")

    st.markdown("---")
    st.subheader("🛒 Selecionar Insumos para a Receita")

    try:
        df_insumos_ft = pd.read_sql("SELECT id, nome, marca, unidade, custo_real_unitario FROM insumos ORDER BY nome", conn)
    except:
        try:
            conn.rollback()
        except:
            pass
        df_insumos_ft = pd.DataFrame()

    if df_insumos_ft.empty:
        st.warning("⚠️ Cadastre seus insumos na aba 'Insumos' antes de montar as fichas técnicas!")
    else:
        if 'itens_receita' not in st.session_state:
            st.session_state.itens_receita = []

        col_sel1, col_sel2, col_sel3 = st.columns([3, 2, 1])
        with col_sel1:
            insumo_escolhido = st.selectbox(
                "Insumo", 
                df_insumos_ft.apply(lambda r: f"{r['id']} - {r['nome']} ({r['marca']})", axis=1).tolist(),
                key="select_insumo_ft_unico"
            )
        with col_sel2:
            qtd_usada = st.number_input("Qtd usada (g, ml ou un)", min_value=0.01, value=100.0, key="input_qtd_usada_unico")
        with col_sel3:
            st.write("")
            st.write("")
            if st.button("➕ Adicionar", key="btn_add_insumo_unico"):
                ins_id = int(insumo_escolhido.split(" - ")[0])
                st.session_state.itens_receita.append({"insumo_id": ins_id, "quantidade": qtd_usada})
                st.success("Item adicionado à lista!")

        if st.session_state.itens_receita:
            st.write("### 📋 Ingredientes Adicionados nesta Receita:")
            
            lista_tabela = []
            for item in st.session_state.itens_receita:
                dados_ins = df_insumos_ft[df_insumos_ft['id'] == item['insumo_id']].iloc[0]
                lista_tabela.append({
                    "id_oculto": item['insumo_id'],
                    "Insumo": dados_ins['nome'],
                    "Marca": dados_ins['marca'],
                    "Qtd Usada": float(item['quantidade']),
                    "Unidade": dados_ins['unidade'],
                    "Custo Parcial (R$)": float(dados_ins['custo_real_unitario'] * item['quantidade']),
                    "custo_base": float(dados_ins['custo_real_unitario'])
                })

            df_tabela = pd.DataFrame(lista_tabela)

            # Tabela interativa onde você pode digitar a Qtd Usada
            df_editado = st.data_editor(
                df_tabela,
                column_config={
                    "id_oculto": None, 
                    "custo_base": None,
                    "Insumo": st.column_config.Column(disabled=True),
                    "Marca": st.column_config.Column(disabled=True),
                    "Unidade": st.column_config.Column(disabled=True),
                    "Custo Parcial (R$)": st.column_config.NumberColumn(disabled=True, format="R$ %.2f"),
                    "Qtd Usada": st.column_config.NumberColumn("Qtd Usada (✏️ Edite aqui)", min_value=0.01)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_itens_receita_unico"
            )

            mudou = False
            custo_total_receita = 0.0
            novos_itens = []

            for index, row in df_editado.iterrows():
                qtd_editada = row['Qtd Usada']
                qtd_original = df_tabela.iloc[index]['Qtd Usada']
                
                if qtd_editada != qtd_original:
                    mudou = True
                
                custo_total_receita += (row['custo_base'] * qtd_editada)
                novos_itens.append({"insumo_id": row['id_oculto'], "quantidade": qtd_editada})

            if mudou:
                st.session_state.itens_receita = novos_itens
                st.rerun()

        # --- ÁREA PARA REMOVER UM INSUMO ESPECÍFICO ---
        if len(st.session_state.itens_receita) > 0:
            st.markdown("---")
            
            ids_na_memoria = tuple([item["insumo_id"] for item in st.session_state.itens_receita])
            
            if ids_na_memoria:
                df_nomes_banco = pd.read_sql("SELECT id, nome FROM insumos WHERE id IN %s", conn, params=(ids_na_memoria,))
                dicionario_nomes = dict(zip(df_nomes_banco['id'], df_nomes_banco['nome']))
                
                col_del1, col_del2 = st.columns([3, 1])
                with col_del1:
                    posicoes = list(range(len(st.session_state.itens_receita)))
                    
                    def formatar_nome_dropdown(i):
                        id_insumo = st.session_state.itens_receita[i]["insumo_id"]
                        nome_insumo = dicionario_nomes.get(id_insumo, "Desconhecido")
                        qtd = st.session_state.itens_receita[i]["quantidade"]
                        return f"Linha {i+1}: {nome_insumo} (Qtd: {qtd})"
                        
                    item_escolhido = st.selectbox(
                        "Qual ingrediente deseja remover?", 
                        posicoes, 
                        format_func=formatar_nome_dropdown
                    )
                    
                with col_del2:
                    st.write("") 
                    if st.button("🗑️ Remover Escolhido", use_container_width=True):
                        st.session_state.itens_receita.pop(item_escolhido)
                        st.rerun()
            st.markdown("---")
        # ----------------------------------------------
            
            st.metric("💰 Custo Total de Produção da Receita", f"R$ {custo_total_receita:.2f}")
            st.metric("🍰 Custo por Unidade / Porção", f"R$ {custo_total_receita / rendimento:.2f}")

            if st.button("💾 Salvar Ficha Técnica Completa", key="btn_salvar_receita_definitivo"):
                if nome_receita.strip() == "":
                    st.error("Por favor, preencha o Nome da Receita antes de salvar.")
                else:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO receitas (nome, rendimento_unidades, peso_total_g) 
                            VALUES (%s, %s, %s)
                            ON CONFLICT (nome) DO UPDATE 
                            SET rendimento_unidades = EXCLUDED.rendimento_unidades, peso_total_g = EXCLUDED.peso_total_g
                            RETURNING id;
                        """, (nome_receita, rendimento, peso_total))
                        rec_id = cursor.fetchone()[0]

                        cursor.execute("DELETE FROM receita_itens WHERE receita_id = %s", (rec_id,))

                        for item in st.session_state.itens_receita:
                            cursor.execute("""
                                INSERT INTO receita_itens (receita_id, insumo_id, quantidade_usada)
                                VALUES (%s, %s, %s)
                            """, (rec_id, item['insumo_id'], item['quantidade']))

                        conn.commit()
                        st.success(f"Ficha técnica da receita '{nome_receita}' salva com sucesso!")
                        st.session_state.itens_receita = []
                        st.rerun()
                    except Exception as err:
                        try:
                            conn.rollback()
                        except:
                            pass
                        st.error(f"Erro ao salvar ficha técnica: {err}")

# === ÁREA PARA VISUALIZAR AS RECEITAS SALVAS ===
    st.markdown("---")
    st.subheader("📖 As Minhas Receitas Salvas")
    
    # 1. Função super leve, sem base de dados, só para preparar a memória
    def preparar_edicao(nome, rend, peso, itens):
        st.session_state["input_nome_receita_unico"] = nome
        st.session_state["input_rendimento_unico"] = float(rend)
        st.session_state["input_peso_total_unico"] = float(peso)
        st.session_state.itens_receita = itens

    # 2. Mostramos as receitas salvas
    try:
        df_receitas = pd.read_sql("SELECT id, nome, rendimento_unidades, peso_total_g FROM receitas ORDER BY nome", conn)
    except Exception:
        df_receitas = pd.DataFrame()
        
    if not df_receitas.empty:
        receita_selecionada = st.selectbox(
            "Pesquisar receita salva:", 
            df_receitas['nome'].tolist(), 
            index=None, 
            placeholder="Escolha uma receita para visualizar..."
        )
        
        if receita_selecionada:
            dados_rec = df_receitas[df_receitas['nome'] == receita_selecionada].iloc[0]
            
            # Adicionamos o "ri.insumo_id" aqui para sabermos exatamente qual o ID a editar
            query_itens = """
                SELECT ri.insumo_id, i.nome as "Insumo", i.marca as "Marca", ri.quantidade_usada as "Qtd Usada", 
                       i.unidade as "Unidade", i.custo_real_unitario,
                       (ri.quantidade_usada * i.custo_real_unitario) as "Custo Parcial"
                FROM receita_itens ri
                JOIN insumos i ON ri.insumo_id = i.id
                WHERE ri.receita_id = %s
            """
            try:
                df_itens_salvos = pd.read_sql(query_itens, conn, params=(int(dados_rec['id']),))
                
                if not df_itens_salvos.empty:
                    custo_total = df_itens_salvos['Custo Parcial'].sum()
                    custo_unidade = custo_total / float(dados_rec['rendimento_unidades'])
                    
                    st.write(f"**Rendimento:** {dados_rec['rendimento_unidades']} unidades/porções | **Peso Total:** {dados_rec['peso_total_g']}g")
                    
                    st.dataframe(
                        df_itens_salvos,
                        column_config={
                            "insumo_id": None, # Esconde o ID técnico
                            "custo_real_unitario": None, 
                            "Custo Parcial": st.column_config.NumberColumn("Custo Parcial (R$)", format="R$ %.2f"),
                            "Qtd Usada": st.column_config.NumberColumn("Qtd Usada", format="%.2f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Preparamos a "marmita" de ingredientes para enviar para o botão de edição
                    itens_para_editar = [
                        {"insumo_id": int(row['insumo_id']), "quantidade": float(row['Qtd Usada'])} 
                        for _, row in df_itens_salvos.iterrows()
                    ]
                    
                    # 3. Botões na base da receita
                    col_tot1, col_tot2, col_tot3, col_tot4 = st.columns([3, 3, 2, 2])
                    with col_tot1:
                        st.info(f"💰 Custo Total: **R$ {custo_total:.2f}**")
                    with col_tot2:
                        st.success(f"🍰 Custo/Unidade: **R$ {custo_unidade:.2f}**")
                    with col_tot3:
                        st.button(
                            "✏️ Editar", 
                            key=f"edit_rec_{dados_rec['id']}", 
                            on_click=preparar_edicao, 
                            args=(dados_rec['nome'], dados_rec['rendimento_unidades'], dados_rec['peso_total_g'], itens_para_editar)
                        )
                    with col_tot4:
                        if st.button("🗑️ Excluir", key=f"del_rec_{dados_rec['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM receitas WHERE id = %s", (int(dados_rec['id']),))
                            conn.commit()
                            st.rerun()
            except Exception as e:
                st.error(f"Erro ao carregar os ingredientes: {e}")
    else:
        st.info("Nenhuma ficha técnica guardada ainda.")
        
elif menu == "💲 Precificação Inteligente":
    st.header("Simulador de Preço por Canal de Venda")
    receitas_df = fetch_data("SELECT * FROM receitas")
    
    if receitas_df.empty:
        st.warning("Cadastre uma receita primeiro na aba 'Fichas Técnicas'.")
    else:
        rec_sel = st.selectbox("Selecione o Doce para Precificar", receitas_df["nome"].tolist())
        rec_data = receitas_df[receitas_df["nome"] == rec_sel].iloc[0]
        
        # Cálculo dos Custos
        df_custos = fetch_data("SELECT ri.quantidade_usada, i.custo_real_unitario FROM receita_itens ri JOIN insumos i ON ri.insumo_id = i.id WHERE ri.receita_id = %s", (int(rec_data["id"]),))
        cmv_unit = (df_custos["quantidade_usada"] * df_custos["custo_real_unitario"]).sum() / float(rec_data["rendimento_unidades"])
        
        total_cf = float(fetch_data("SELECT SUM(valor_mensal) as t FROM custos_fixos").iloc[0]["t"] or 0)
        hr_mes = fetch_data("SELECT horas_trabalhadas_mes FROM config_negocio").iloc[0]["horas_trabalhadas_mes"]
        custo_min = (float(total_cf) / float(hr_mes)) / 60 if hr_mes > 0 else 0
        tempo_preparo = st.number_input("⏳ Tempo de preparo da receita inteira (em minutos)", min_value=1, value=60)
        custo_op_unit = (custo_min * tempo_preparo) / float(rec_data["rendimento_unidades"])
        custo_total = float(cmv_unit) + custo_op_unit
        
        st.markdown("### 1. Custo Real do Doce")
        col_img, col_txt = st.columns([1, 4])
        if rec_data["imagem_base64"]:
            col_img.image(base64.b64decode(rec_data["imagem_base64"]), width=120)
        col_txt.write(f"**Ingredientes (CMV):** R$ {cmv_unit:.2f}")
        col_txt.write(f"**Gastos Fixos (Rateio):** R$ {custo_op_unit:.2f}")
        col_txt.info(f"**Custo Total (Para não ter prejuízo): R$ {custo_total:.2f}**")
        
        st.markdown("---")
        st.markdown("### 2. Configure suas Taxas Atuais")
        st.write("Altere as porcentagens livremente abaixo. Os preços sugeridos serão recalculados na hora.")
        
        margem = st.slider("Margem de Lucro Desejada (%)", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
        
        c1, c2, c3, c4 = st.columns(4)
        taxa_pix = c1.number_input("Taxa Pix/Dinheiro (%)", value=0.0, step=0.5)
        taxa_cartao = c2.number_input("Taxa Maquininha (%)", value=3.5, step=0.5)
        taxa_vr = c3.number_input("Taxa VR/Alelo (%)", value=6.5, step=0.5)
        taxa_ifood = c4.number_input("Taxa iFood (%)", value=27.0, step=0.5)
        
        st.markdown("---")
        st.markdown("### 3. Preços Mínimos Sugeridos")
        st.caption("Cobrando esses valores, sua margem de lucro em dinheiro será exatamente a mesma em qualquer canal, pois as taxas já estão cobertas.")
        
        def calc_preco(custo, mrg, tx):
            fator = 1 - ((mrg + tx) / 100)
            return (custo / fator) if fator > 0 else 0
            
        p_pix = calc_preco(custo_total, float(margem), float(taxa_pix))
        p_cartao = calc_preco(custo_total, float(margem), float(taxa_cartao))
        p_vr = calc_preco(custo_total, float(margem), float(taxa_vr))
        p_ifood = calc_preco(custo_total, float(margem), float(taxa_ifood))
        
        res1, res2, res3, res4 = st.columns(4)
        res1.metric("💰 Pix / Dinheiro", f"R$ {p_pix:.2f}")
        res2.metric("💳 Maquininha", f"R$ {p_cartao:.2f}")
        res3.metric("🍽️ Vale Refeição", f"R$ {p_vr:.2f}")
        res4.metric("🛵 iFood", f"R$ {p_ifood:.2f}")

elif menu == "💸 Fluxo de Caixa":
    st.header("Registrar Entradas e Saídas")
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("caixa"):
            tipo = st.radio("Tipo", ["Entrada", "Saída"])
            cat = st.selectbox("Categoria", ["Vendas", "Insumos", "Custos Fixos", "Taxas/Impostos", "Outros"])
            desc = st.text_input("Descrição")
            val = st.number_input("Valor (R$)", min_value=0.01)
            if st.form_submit_button("Registrar"):
                run_query("INSERT INTO fluxo_caixa (data, tipo, categoria, descricao, valor) VALUES (%s, %s, %s, %s, %s)", (datetime.today().strftime("%Y-%m-%d"), tipo, cat, desc, val))
                st.success("Registrado!")
                st.rerun()
    with col2:
        df_caixa = fetch_data("SELECT data, tipo, descricao, valor FROM fluxo_caixa ORDER BY id DESC LIMIT 15")
        st.dataframe(df_caixa)

elif menu == "📊 Ponto de Equilíbrio & DRE":
    st.header("DRE e Ponto de Equilíbrio (Break-Even)")
    
    df_dre = fetch_data("SELECT tipo, categoria, valor FROM fluxo_caixa")
    total_cf = float(fetch_data("SELECT SUM(valor_mensal) as t FROM custos_fixos").iloc[0]["t"] or 0)
    dias_trabalhados = float(fetch_data("SELECT dias_trabalhados_mes FROM config_negocio").iloc[0]["dias_trabalhados_mes"])
    
    if not df_dre.empty:
        rec_bruta = float(df_dre[df_dre['tipo'] == 'Entrada']['valor'].sum())
        custos_var = float(df_dre[(df_dre['tipo'] == 'Saída') & (df_dre['categoria'] == 'Insumos')]['valor'].sum())
        
        margem_contribuicao_pct = ((rec_bruta - custos_var) / rec_bruta) if rec_bruta > 0 else 0.30
        
        ponto_equilibrio_mensal = total_cf / margem_contribuicao_pct if margem_contribuicao_pct > 0 else 0
        ponto_equilibrio_diario = ponto_equilibrio_mensal / dias_trabalhados if dias_trabalhados > 0 else 0
        
        st.subheader("🎯 Suas Metas de Sobrevivência")
        col1, col2 = st.columns(2)
        col1.metric("Meta de Faturamento MENSAL", f"R$ {ponto_equilibrio_mensal:.2f}", help="Tudo o que vender acima disso é lucro real.")
        col2.metric(f"Meta DIÁRIA ({dias_trabalhados} dias/mês)", f"R$ {ponto_equilibrio_diario:.2f}")
        
        st.markdown("---")
        st.subheader("Resumo do Mês (DRE)")
        lucro = rec_bruta - float(df_dre[df_dre['tipo'] == 'Saída']['valor'].sum())
        st.write(f"**Receita Bruta:** R$ {rec_bruta:.2f}")
        st.write(f"**Lucro Líquido Atual:** R$ {lucro:.2f}")
    else:
        st.warning("Registre movimentações no Fluxo de Caixa para ver sua DRE e Ponto de Equilíbrio.")

conn.close()

if menu == "🛒 Estoque & Compras":
    st.header("Controle de Estoque e Lista de Compras")
    
    # Função segura e isolada para esta aba, evitando conflitos de conexão
    def carregar_estoque_seguro():
        try:
            cursor = conn.cursor()
            # Garante que a coluna existe
            cursor.execute("ALTER TABLE insumos ADD COLUMN IF NOT EXISTS estoque_minimo NUMERIC DEFAULT 0;")
            conn.commit()
            
            # Puxa os dados diretamente para um DataFrame
            query = "SELECT id, nome, marca, unidade, estoque_atual, estoque_minimo FROM insumos ORDER BY nome"
            df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            return pd.DataFrame()

    df_estoque = carregar_estoque_seguro()

    if df_estoque.empty:
        st.info("Nenhum insumo cadastrado ainda ou tabela vazia. Vá à aba de Insumos para cadastrar o primeiro item!")
    else:
        st.subheader("📦 Atualização Rápida de Estoque")
        st.write("Edite as quantidades diretamente na tabela abaixo e clique em Salvar!")
        
        # Tabela interativa para edição rápida
        df_editado = st.data_editor(
            df_estoque,
            column_config={
                "id": None, # Esconde a coluna ID
                "nome": st.column_config.TextColumn("Insumo", disabled=True),
                "marca": st.column_config.TextColumn("Marca", disabled=True),
                "unidade": st.column_config.TextColumn("Unid.", disabled=True),
                "estoque_atual": st.column_config.NumberColumn("Estoque Atual", min_value=0.0, format="%.2f"),
                "estoque_minimo": st.column_config.NumberColumn("Estoque Mínimo (Alerta)", min_value=0.0, format="%.2f")
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("💾 Salvar Estoque Atualizado"):
            try:
                cursor = conn.cursor()
                for index, row in df_editado.iterrows():
                    cursor.execute(
                        "UPDATE insumos SET estoque_atual=%s, estoque_minimo=%s WHERE id=%s", 
                        (row['estoque_atual'], row['estoque_minimo'], row['id'])
                    )
                conn.commit()
                st.success("Tudo atualizado! Suas quantidades foram salvas.")
                st.rerun()
            except Exception as ex:
                try:
                    conn.rollback()
                except:
                    pass
                st.error(f"Erro ao salvar: {ex}")
            
        st.markdown("---")
        st.subheader("🛒 Sua Lista de Compras")
        
        # Filtra automaticamente quem está com o estoque abaixo ou abaixo/igual ao mínimo
        df_compras = df_editado[df_editado['estoque_atual'] <= df_editado['estoque_minimo']]
        
        if df_compras.empty:
            st.success("🎉 Tudo em dia! Você não tem nenhum item abaixo do estoque mínimo.")
        else:
            st.warning(f"Atenção: Você tem {len(df_compras)} itens precisando de reposição!")
            st.dataframe(
                df_compras[['nome', 'marca', 'estoque_atual', 'estoque_minimo', 'unidade']], 
                hide_index=True,
                use_container_width=True
            )
