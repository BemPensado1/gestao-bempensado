import streamlit as st
import psycopg2
import pandas as pd
import base64
from datetime import datetime

st.set_page_config(page_title="Gestão Bem Pensado", page_icon="🧁", layout="wide")

# Conexão segura com o Supabase usando a chave secreta
@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

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
st.sidebar.title("🧁 Bem Pensado")
menu = st.sidebar.radio("Navegação", ["📦 Insumos", "🏢 Custos Fixos", "📸 Fichas Técnicas", "💲 Precificação Inteligente", "💸 Fluxo de Caixa", "📊 Ponto de Equilíbrio & DRE"])

# Funções auxiliares
def run_query(query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        conn.commit()

def fetch_data(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

# --- MÓDULOS ---

if menu == "📦 Insumos":
    st.header("Cadastro de Insumos & Fator de Correção")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("form_insumo", clear_on_submit=True):
            nome = st.text_input("Nome do Insumo")
            unidade = st.selectbox("Unidade de Uso", ["g", "ml", "unid"])
            preco = st.number_input("Preço Pago (R$)", min_value=0.01)
            peso_bruto = st.number_input("Peso Total Comprado", min_value=0.01)
            peso_liquido = st.number_input("Peso Real Aproveitado", min_value=0.01)
            est_atual = st.number_input("Estoque Atual", min_value=0.0)
            if st.form_submit_button("Cadastrar Insumo"):
                fc = peso_bruto / peso_liquido
                custo_real = (preco / peso_bruto) * fc
                run_query("INSERT INTO insumos (nome, unidade, preco_compra, peso_bruto, peso_liquido, fator_correcao, custo_real_unitario, estoque_atual) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (nome) DO NOTHING", 
                          (nome, unidade, preco, peso_bruto, peso_liquido, fc, custo_real, est_atual))
                st.success("Salvo com sucesso!")
                st.rerun()
    with col2:
        df_ins = fetch_data("SELECT nome, fator_correcao, custo_real_unitario, estoque_atual FROM insumos")
        st.dataframe(df_ins)

elif menu == "🏢 Custos Fixos":
    st.header("Custos Operacionais e Hora de Trabalho")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("form_custo"):
            nome = st.text_input("Descrição (Ex: DAS, Aluguel, Luz)")
            valor = st.number_input("Valor Mensal (R$)", min_value=0.01)
            if st.form_submit_button("Salvar Custo Fixo"):
                run_query("INSERT INTO custos_fixos (nome, valor_mensal) VALUES (%s, %s) ON CONFLICT (nome) DO UPDATE SET valor_mensal = EXCLUDED.valor_mensal", (nome, valor))
                st.success("Salvo!")
                st.rerun()
        
        st.write("---")
        dias_mes = st.number_input("Quantos dias você trabalha no mês?", value=22)
        horas_mes = st.number_input("Quantas horas por mês?", value=160)
        if st.button("Atualizar Jornada"):
            run_query("UPDATE config_negocio SET dias_trabalhados_mes = %s, horas_trabalhadas_mes = %s WHERE id = 1", (dias_mes, horas_mes))
            st.success("Jornada atualizada!")
    with col2:
        df_cf = fetch_data("SELECT nome, valor_mensal FROM custos_fixos")
        st.dataframe(df_cf)
        st.metric("Total Custos Fixos", f"R$ {df_cf['valor_mensal'].sum():.2f}")

elif menu == "📸 Fichas Técnicas":
    st.header("Montar Ficha Técnica com Foto")
    insumos_df = fetch_data("SELECT id, nome, unidade, custo_real_unitario FROM insumos")
    
    if insumos_df.empty:
        st.warning("Cadastre insumos primeiro.")
    else:
        nome_receita = st.text_input("Nome da Receita")
        col1, col2 = st.columns(2)
        rendimento = col1.number_input("Rendimento (Unidades)", min_value=1.0)
        tempo = col2.number_input("Tempo de Preparo (Minutos)", min_value=1.0)
        foto = st.file_uploader("Foto do Produto Final (Opcional)", type=["jpg", "png", "jpeg"])
        
        if "itens_receita" not in st.session_state:
            st.session_state.itens_receita = []
            
        col_ins, col_qtd, col_btn = st.columns([3, 2, 1])
        insumo_nome = col_ins.selectbox("Insumo", insumos_df["nome"].tolist())
        row_ins = insumos_df[insumos_df["nome"] == insumo_nome].iloc[0]
        qtd_usada = col_qtd.number_input(f"Quantidade ({row_ins['unidade']})", min_value=0.01)
        if col_btn.button("Adicionar Ingrediente"):
            st.session_state.itens_receita.append({"insumo_id": int(row_ins["id"]), "nome": insumo_nome, "quantidade": float(qtd_usada)})
                
        if st.session_state.itens_receita:
            st.dataframe(pd.DataFrame(st.session_state.itens_receita)[['nome', 'quantidade']])
            if st.button("Salvar Receita Completa"):
                foto_b64 = base64.b64encode(foto.read()).decode("utf-8") if foto else ""
                run_query("INSERT INTO receitas (nome, rendimento, tempo_preparo_minutos, imagem_base64) VALUES (%s, %s, %s, %s) ON CONFLICT (nome) DO NOTHING", (nome_receita, rendimento, tempo, foto_b64))
                rec_id = fetch_data("SELECT id FROM receitas WHERE nome = %s", (nome_receita,)).iloc[0]['id']
                for item in st.session_state.itens_receita:
                    run_query("INSERT INTO receita_itens (receita_id, insumo_id, quantidade) VALUES (%s, %s, %s)", (int(rec_id), int(item["insumo_id"]), item["quantidade"]))
                st.success("Receita Salva!")
                st.session_state.itens_receita = []
                st.rerun()

elif menu == "💲 Precificação Inteligente":
    st.header("Simulador de Preço por Canal de Venda")
    receitas_df = fetch_data("SELECT * FROM receitas")
    
    if receitas_df.empty:
        st.warning("Cadastre uma receita primeiro na aba 'Fichas Técnicas'.")
    else:
        rec_sel = st.selectbox("Selecione o Doce para Precificar", receitas_df["nome"].tolist())
        rec_data = receitas_df[receitas_df["nome"] == rec_sel].iloc[0]
        
        # Cálculo dos Custos
        df_custos = fetch_data("SELECT ri.quantidade, i.custo_real_unitario FROM receita_itens ri JOIN insumos i ON ri.insumo_id = i.id WHERE ri.receita_id = %s", (int(rec_data["id"]),))
        cmv_unit = (df_custos["quantidade"] * df_custos["custo_real_unitario"]).sum() / float(rec_data["rendimento"]) if not df_custos.empty else 0
        
        total_cf = float(fetch_data("SELECT SUM(valor_mensal) as t FROM custos_fixos").iloc[0]["t"] or 0)
        hr_mes = fetch_data("SELECT horas_trabalhadas_mes FROM config_negocio").iloc[0]["horas_trabalhadas_mes"]
        custo_min = (float(total_cf) / float(hr_mes)) / 60 if hr_mes > 0 else 0
        custo_op_unit = (custo_min * float(rec_data["tempo_preparo_minutos"])) / float(rec_data["rendimento"])
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
