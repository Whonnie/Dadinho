import streamlit as st
import random
from collections import Counter
from supabase import create_client, Client
import time

# -------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO INTERFACE PREMIUM (Feltro de Cassino)
# -------------------------------------------------------------------------
st.set_page_config(page_title="Dadinhos - Clara & Júlia", layout="wide")

st.markdown("""
    <style>
    /* Força o fundo de toda a aplicação para o verde cassino escuro */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #064e3b !important;
    }
    
    /* Placar Lateral Robusto */
    .tabela-pontos {
        background-color: #022c22 !important;
        border: 3px solid #fbbf24 !important;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.6);
    }
    
    /* Retângulo escuro premium unificado no topo do placar para o Total */
    .caixa-total-topo {
        background-color: #011612 !important;
        border: 2px solid #fbbf24 !important;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: inset 0px 2px 5px rgba(0,0,0,0.8);
    }
    
    .caixa-pontos-salva {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #64748b !important;
        text-align: center;
        padding: 6px 0;
        font-weight: bold;
        font-size: 16px;
        border-radius: 8px;
        box-shadow: inset 0px 2px 4px rgba(0,0,0,0.4);
    }
    
    .divisor-pontos {
        border-bottom: 1px dashed rgba(255, 255, 255, 0.15);
        margin: 8px 0;
    }
    
    .linha-placar {
        color: #ffffff !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        display: flex;
        align-items: center;
        height: 100%;
    }
    
    .titulo-dourado {
        color: #fbbf24 !important;
        font-family: 'Georgia', serif;
        font-weight: bold;
        text-align: center;
        margin-bottom: 15px;
    }
    
    .tela-transicao {
        background-color: #022c22;
        border: 4px solid #fbbf24;
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.7);
        margin: 8px auto;
        max-width: 600px;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# CONEXÃO COM O BANCO DE DADOS ONLINE (SUPABASE)
# -------------------------------------------------------------------------
SUPABASE_URL = "https://tgjducfzbgkcewipvyqi.supabase.co"
SUPABASE_KEY = "sb_secret_6Vbs8RdTFpD-2Q8QmTU5Wg_0kaw585G"

@st.cache_resource
def iniciar_conexao_banco() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = iniciar_conexao_banco()

def baixar_estado_do_jogo():
    try:
        resposta = supabase.from_("partida").select("*").eq("id", 1).execute()
        if resposta.data:
            return resposta.data[0]
    except Exception as e:
        st.error(f"Erro técnico de conexão: {e}")
    return None

def salvar_estado_no_banco(dados_atualizados):
    try:
        supabase.from_("partida").update(dados_atualizados).eq("id", 1).execute()
    except Exception as e:
        st.error(f"Erro ao salvar jogada: {e}")

# -------------------------------------------------------------------------
# MATEMÁTICA E REGRAS DOS DADINHOS
# -------------------------------------------------------------------------
def obter_valores_finais_dados(dados_mesa):
    valores_normais = [d["valor"] for d in dados_mesa if d.get("valor") is not None]
    if not valores_normais:
        return []
        
    valores_naturais = []
    for d in dados_mesa:
        if d.get("valor") is not None:
            if d.get("veio_por_debajo") and not d["salvo"]:
                valores_naturais.append(7 - d["valor"])
            else:
                valores_naturais.append(d["valor"])

    if len(set(valores_naturais)) == 1:
        return valores_naturais
    return valores_normais

def verificar_combinacoes_mesa(dados_mesa):
    valores_finais = obter_valores_finais_dados(dados_mesa)
    if not valores_finais or len(valores_finais) < 5:
        return {"escaleira": False, "full_house": False, "quadra": False, "tuti": False}
        
    contagem = Counter(valores_finais)
    valores_unicos = sorted(list(set(valores_finais)))

    return {
        "escaleira": (valores_unicos == [1, 2, 3, 4, 5] or valores_unicos == [2, 3, 4, 5, 6] or valores_unicos == [1, 3, 4, 5, 6]),
        "full_house": (sorted(list(contagem.values())) == [2, 3]),
        "quadra": any(qtd >= 4 for qtd in contagem.values()),
        "tuti": (len(set(valores_finais)) == 1)
    }

def calcular_pontos_possiveis(dados_mesa, jogada_de_primeira):
    valores = obter_valores_finais_dados(dados_mesa)
    opcoes = {i: 0 for i in range(1, 7)}
    opcoes.update({"escaleira": 0, "full_house": 0, "quadra": 0, "tuti": 0})
    
    if not valores or len(valores) < 5:
        return opcoes
        
    contagem = Counter(valores)
    for i in range(1, 7):
        opcoes[i] = contagem[i] * i

    mesa = verificar_combinacoes_mesa(dados_mesa)
    opcoes["escaleira"] = (25 if jogada_de_primeira else 20) if mesa["escaleira"] else 0
    opcoes["full_house"] = (35 if jogada_de_primeira else 30) if mesa["full_house"] else 0
    opcoes["quadra"] = (45 if jogada_de_primeira else 40) if mesa["quadra"] else 0
    opcoes["tuti"] = (100 if jogada_de_primeira else 50) if mesa["tuti"] else 0

    return opcoes

# -------------------------------------------------------------------------
# INTERAÇÃO DAS JOGADAS (Ações Gravadas na Nuvem)
# -------------------------------------------------------------------------
def alternar_salvamento_dado(idx, estado):
    if estado["dados_rolados_nesta_rodada"]:
        dados_novos = estado["dados"]
        dados_novos[idx]["salvo"] = not dados_novos[idx]["salvo"]
        salvar_estado_no_banco({"dados": dados_novos})

def alternar_por_debajo(estado):
    salvar_estado_no_banco({"por_debajo_ativo": not estado["por_debajo_ativo"]})

def rolar_dados_web(estado):
    if estado["lancamentos_restantes"] > 0:
        lancamentos = estado["lancamentos_restantes"]
        jogada_primeira = estado["jogada_de_primeira"]
        if lancamentos < 3:
            jogada_primeira = False

        dados_novos = estado["dados"]
        st.session_state["animar_rolagem_normal"] = True
        if estado["por_debajo_ativo"]:
            st.session_state["animar_por_debajo"] = True

        for i in range(5):
            if not dados_novos[i]["salvo"]:
                dados_novos[i]["valor"] = random.randint(1, 6)
                dados_novos[i]["veio_por_debajo"] = False

        if not estado["por_debajo_ativo"]:
            salvar_estado_no_banco({
                "dados": dados_novos,
                "lancamentos_restantes": lancamentos - 1,
                "jogada_de_primeira": jogada_primeira,
                "dados_rolados_nesta_rodada": True,
                "por_debajo_ativo": False
            })
        else:
            salvar_estado_no_banco({
                "dados": dados_novos,
                "lancamentos_restantes": lancamentos - 1,
                "jogada_de_primeira": jogada_primeira,
                "dados_rolados_nesta_rodada": True
            })

def reiniciar_partida_completa():
    dados_iniciais = [
        {"valor": None, "salvo": False, "veio_por_debajo": False, "cor": "#F8F23B", "texto": "#000000"},
        {"valor": None, "salvo": False, "veio_por_debajo": False, "cor": "#F8F23B", "texto": "#000000"},
        {"valor": None, "salvo": False, "veio_por_debajo": False, "cor": "#F8F23B", "texto": "#000000"},
        {"valor": None, "salvo": False, "veio_por_debajo": False, "cor": "#F81919", "texto": "#FFFFFF"},
        {"valor": None, "salvo": False, "veio_por_debajo": False, "cor": "#F81919", "texto": "#FFFFFF"}
    ]
    pontuacao_vazia = {
        "Clara": {"1": None, "2": None, "3": None, "4": None, "5": None, "6": None, "escaleira": None, "full_house": None, "quadra": None, "tuti": None},
        "Júlia": {"1": None, "2": None, "3": None, "4": None, "5": None, "6": None, "escaleira": None, "full_house": None, "quadra": None, "tuti": None}
    }
    bonus_vazio = {
        "Clara": {"escaleira": 0, "full_house": 0, "quadra": 0, "tuti": 0},
        "Júlia": {"escaleira": 0, "full_house": 0, "quadra": 0, "tuti": 0}
    }
    
    # DEFINE ALEATORIAMENTE QUEM COMEÇA
    jogador_inicial = random.choice(["Clara", "Júlia"])
    
    salvar_estado_no_banco({
        "turno_atual": jogador_inicial,
        "lancamentos_restantes": 3,
        "por_debajo_ativo": False,
        "jogada_de_primeira": True,
        "dados_rolados_nesta_rodada": False,
        "dados": dados_iniciais,
        "pontuacao": pontuacao_vazia,
        "bonus_repeticao": bonus_vazio,
        "mostrar_tela_transicao": False
    })
    st.rerun()

def selecionar_slot_pontuacao(slot_chave, estado):
    previa = calcular_pontos_possiveis(estado["dados"], estado["jogada_de_primeira"])
    pontos_a_guardar = previa.get(slot_chave, 0)
    
    pontuacao = estado["pontuacao"]
    bonus_rep = estado["bonus_repeticao"]
    jogador = estado["turno_atual"]
    mesa = verificar_combinacoes_mesa(estado["dados"])

    str_chave = str(slot_chave)

    if mesa["escaleira"] and pontuacao[jogador].get("escaleira") is not None: bonus_rep[jogador]["escaleira"] += 1
    if mesa["full_house"] and pontuacao[jogador].get("full_house") is not None: bonus_rep[jogador]["full_house"] += 1
    if mesa["quadra"] and pontuacao[jogador].get("quadra") is not None: bonus_rep[jogador]["quadra"] += 1
    if mesa["tuti"]:
        if pontuacao[jogador].get("tuti") is not None:
            pontos_a_guardar = 50
            bonus_rep[jogador]["tuti"] += 1

    pontuacao[jogador][str_chave] = pontos_a_guardar
    proximo_jogador = "Júlia" if jogador == "Clara" else "Clara"

    dados_limpos = estado["dados"]
    for d in dados_limpos:
        d["valor"] = None
        d["salvo"] = False
        d["veio_por_debajo"] = False

    salvar_estado_no_banco({
        "pontuacao": pontuacao,
        "bonus_repeticao": bonus_rep,
        "turno_atual": proximo_jogador,
        "lancamentos_restantes": 3,
        "jogada_de_primeira": True,
        "dados_rolados_nesta_rodada": False,
        "dados": dados_limpos,
        "por_debajo_ativo": False,
        "mostrar_tela_transicao": True
    })
    st.rerun()

def fechar_tela_transicao():
    salvar_estado_no_banco({"mostrar_tela_transicao": False})
    st.rerun()

# -------------------------------------------------------------------------
# FRAGMENTO DE AUTO-ATUALIZAÇÃO SIMULTÂNEA (Roda a cada 3 segundos)
# -------------------------------------------------------------------------
@st.fragment(run_every=3)
def renderizar_tabuleiro_sincronizado():
    estado_nuvem = baixar_estado_do_jogo()
    
    if estado_nuvem:
        # LÓGICA DE FIM DE PARTIDA (Coroação)
        fim_clara = all(v is not None for v in estado_nuvem["pontuacao"]["Clara"].values())
        fim_julia = all(v is not None for v in estado_nuvem["pontuacao"]["Júlia"].values())
        
        if fim_clara and fim_julia:
            tot_clara = sum(v for v in estado_nuvem["pontuacao"]["Clara"].values() if v is not None) + sum(q * 5 for q in estado_nuvem["bonus_repeticao"]["Clara"].values())
            tot_julia = sum(v for v in estado_nuvem["pontuacao"]["Júlia"].values() if v is not None) + sum(q * 5 for q in estado_nuvem["bonus_repeticao"]["Júlia"].values())
            
            if tot_clara > tot_julia: vencedora = "Clara"
            elif tot_julia > tot_clara: vencedora = "Júlia"
            else: vencedora = "Empate"
            
            st.markdown(f"""
                <div class='tela-transicao'>
                    <h1 style='color: #fbbf24; font-size: 50px;'>🏆 FIM DE PARTIDA! 🏆</h1>
                    <p style='color: white; font-size: 26px; margin-top:20px;'>Clara: <b>{tot_clara} pts</b> | Júlia: <b>{tot_julia} pts</b></p>
                    <h2 style='color: #10b981; font-size: 38px; margin-top:15px;'>🎉 Parabéns, {vencedora.upper()}! Você ganhou! 🎉</h2>
                    <br>
                </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 JOGAR NOVAMENTE", use_container_width=True, type="primary"):
                reiniciar_partida_completa()
            return

        # LÓGICA DE TELA DE TRANSIÇÃO DE JOGADOR
        if estado_nuvem.get("mostrar_tela_transicao"):
            st.markdown(f"""
                <div class='tela-transicao'>
                    <h1 style='color: #fbbf24; font-size: 40px;'>Fim da Rodada!</h1>
                    <h2 style='color: white; font-size: 28px; margin-top:20px;'>Próxima jogada:</h2>
                    <h1 style='color: #10b981; font-size: 52px; font-weight: bold;'>JOGADA DE {estado_nuvem['turno_atual'].upper()} 🎲</h1>
                    <p style='color: rgba(255,255,255,0.6); font-style:italic; margin-top:10px;'>Clique abaixo para assumir a mesa</p>
                </div>
            """, unsafe_allow_html=True)
            if st.button("✨ COMEÇAR MINHA JOGADA", use_container_width=True, type="primary"):
                fechar_tela_transicao()
            return

        # INTERFACE DO JOGO ATIVO
        col_turn, col_lanc = st.columns([2, 1])
        with col_turn:
            st.markdown(f"<h1 style='color: #10b981; font-family: sans-serif; margin-bottom:0;'>🎲 TURNO ATUAL: {estado_nuvem['turno_atual'].upper()}</h1>", unsafe_allow_html=True)
        with col_lanc:
            st.markdown(f"<h2 style='color: #fbbf24; text-align: right; margin-bottom:0; font-family: sans-serif;'>Lançamentos: {estado_nuvem['lancamentos_restantes']}/3</h2>", unsafe_allow_html=True)

        st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; border-color: #10b981;'>", unsafe_allow_html=True)

        Mesa, Espacador, Placar = st.columns([5, 0.6, 3.5])

        with Mesa:
            st.markdown("<h2 class='titulo-dourado' style='text-align: left;'>Mesa de Dados</h2>", unsafe_allow_html=True)
            container_dados = st.empty()
            
            def animar_grid_dados(dados_para_mostrar):
                with container_dados.container():
                    cols_dados = st.columns(5)
                    for i in range(5):
                        d = dados_para_mostrar[i]
                        borda = "5px solid #fbbf24" if d["salvo"] else "2px solid rgba(255,255,255,0.2)"
                        with cols_dados[i]:
                            st.markdown(f"""
                                <div style="
                                    background-color: {d['cor']}; 
                                    color: {d['texto']}; 
                                    font-size: 54px; 
                                    font-weight: 900; 
                                    text-align: center; 
                                    padding: 15px 0px; 
                                    border-radius: 18px; 
                                    border: {borda};
                                    box-shadow: 4px 4px 12px rgba(0,0,0,0.6);
                                    font-family: 'Arial Black', sans-serif;
                                ">{d['valor'] if d['valor'] is not None else '-'}</div>
                            """, unsafe_allow_html=True)

            if st.session_state.get("animar_rolagem_normal"):
                del st.session_state["animar_rolagem_normal"]
                for _ in range(6):
                    dados_ficticios = []
                    for d in estado_nuvem["dados"]:
                        if d["salvo"]: dados_ficticios.append(d)
                        else: dados_ficticios.append({"valor": random.randint(1, 6), "cor": d["cor"], "texto": d["texto"], "salvo": False})
                    animar_grid_dados(dados_ficticios)
                    time.sleep(0.08)

            if st.session_state.get("animar_por_debajo"):
                del st.session_state["animar_por_debajo"]
                animar_grid_dados(estado_nuvem["dados"])
                time.sleep(0.6)
                
                dados_finais_debajo = estado_nuvem["dados"]
                for _ in range(4):
                    dados_giro = []
                    for d in dados_finais_debajo:
                        if d["salvo"]: dados_giro.append(d)
                        else: dados_giro.append({"valor": random.randint(1,6), "cor": d["cor"], "texto": d["texto"], "salvo": False})
                    animar_grid_dados(dados_giro)
                    time.sleep(0.07)
                    
                for i in range(5):
                    if not dados_finais_debajo[i]["salvo"] and dados_finais_debajo[i]["valor"] is not None:
                        dados_finais_debajo[i]["valor"] = 7 - dados_finais_debajo[i]["valor"]
                        dados_finais_debajo[i]["veio_por_debajo"] = True
                        
                salvar_estado_no_banco({"dados": dados_finais_debajo, "por_debajo_ativo": False})
                st.rerun()

            # Renderização estável (mostra "-" se o valor for None)
            with container_dados.container():
                cols_dados = st.columns(5)
                for i in range(5):
                    d = estado_nuvem["dados"][i]
                    borda = "5px solid #fbbf24" if d["salvo"] else "2px solid rgba(255,255,255,0.2)"
                    with cols_dados[i]:
                        st.markdown(f"""
                            <div style="
                                background-color: {d['cor']}; 
                                color: {d['texto']}; 
                                font-size: 54px; 
                                font-weight: 900; 
                                text-align: center; 
                                padding: 15px 0px; 
                                border-radius: 18px; 
                                border: {borda};
                                box-shadow: 4px 4px 12px rgba(0,0,0,0.6);
                                font-family: 'Arial Black', sans-serif;
                            ">{d['valor'] if d['valor'] is not None else '-'}</div>
                        """, unsafe_allow_html=True)
                        
                        txt_travar = "🔓 Salvo" if d["salvo"] else "🔒 Travar"
                        if st.button(txt_travar, key=f"btn_dado_real_{i}", use_container_width=True):
                            alternar_salvamento_dado(i, estado_nuvem)
                            st.rerun()

            st.markdown("<br><br>", unsafe_allow_html=True)
            
            col_debajo, col_action = st.columns(2)
            with col_debajo:
                cor_botao_debajo = "🔥 POR DEBAJO: ON" if estado_nuvem["por_debajo_ativo"] else "💤 POR DEBAJO: OFF"
                if st.button(cor_botao_debajo, use_container_width=True):
                    alternar_por_debajo(estado_nuvem)
                    st.rerun()
                    
            with col_action:
                if st.button("🎲 ROLAR DADOS", type="primary", use_container_width=True):
                    rolar_dados_web(estado_nuvem)
                    st.rerun()
                    
            st.markdown("<br><hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
            
            if st.button("🔄 ZERAR PARTIDA ATUAL", use_container_width=True):
                reiniciar_partida_completa()

        with Placar:
            st.markdown("<div class='tabela-pontos'>", unsafe_allow_html=True)
            
            # CÁLCULO DINÂMICO DOS TOTAIS
            jogador = estado_nuvem["turno_atual"]
            subtotal = sum(v for v in estado_nuvem["pontuacao"][jogador].values() if v is not None)
            total_bonus_salvo = sum(qtd * 5 for qtd in estado_nuvem["bonus_repeticao"][jogador].values())
            
            bonus_pendente = 0
            if estado_nuvem["dados_rolados_nesta_rodada"]:
                mesa = verificar_combinacoes_mesa(estado_nuvem["dados"])
                for b_chave in ["escaleira", "full_house", "quadra", "tuti"]:
                    if mesa[b_chave] and estado_nuvem["pontuacao"][jogador].get(b_chave) is not None:
                        bonus_pendente += 5
                        
            total_geral = subtotal + total_bonus_salvo + bonus_pendente
            
            # TOTAL INTEGRADO EXCLUSIVAMENTE NO RETÂNGULO DO TOPO DO PLACAR
            st.markdown(f"""
                <div class='caixa-total-topo'>
                    <span style='color: #fbbf24; font-size: 22px; font-weight: bold; font-family: sans-serif;'>
                        TOTAL MESA: {total_geral} PTS
                    </span>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<h2 class='titulo-dourado' style='margin-bottom:15px;'>TABELA DE PONTOS</h2>", unsafe_allow_html=True)
            
            slots_nomes = {
                1: "Jogada de 1", 2: "Jogada de 2", 3: "Jogada de 3",
                4: "Jogada de 4", 5: "Jogada de 5", 6: "Jogada de 6",
                "escaleira": "Escaleira (20 pts)", "full_house": "Full House (30 pts)",
                "quadra": "Quadra (40 pts)", "tuti": "Tuti (50 pts)"
            }
            
            previa_pontos = calcular_pontos_possiveis(estado_nuvem["dados"], estado_nuvem["jogada_de_primeira"]) if estado_nuvem["dados_rolados_nesta_rodada"] else {}
            
            for chave, nome in slots_nomes.items():
                c_nome, c_btn = st.columns([1.8, 1])
                with c_nome:
                    st.markdown(f"<div class='linha-placar'>{nome}</div>", unsafe_allow_html=True)
                with c_btn:
                    str_chave = str(chave)
                    valor_salvo = estado_nuvem["pontuacao"][jogador].get(str_chave)
                    
                    if valor_salvo is not None:
                        st.markdown(f"<div class='caixa-pontos-salva'>{valor_salvo} pts</div>", unsafe_allow_html=True)
                    else:
                        if estado_nuvem["dados_rolados_nesta_rodada"]:
                            pontos_previa = previa_pontos.get(chave, 0)
                            if st.button(f"Anotar ({pontos_previa})", key=f"slot_{chave}", use_container_width=True):
                                selecionar_slot_pontuacao(chave, estado_nuvem)
                                st.rerun()
                        else:
                            st.markdown("<div class='caixa-pontos-salva' style='background-color: transparent; border: 1px dashed rgba(255,255,255,0.2); color: rgba(255,255,255,0.4);'>-</div>", unsafe_allow_html=True)
                st.markdown("<div class='divisor-pontos'></div>", unsafe_allow_html=True)
                            
            st.markdown("<br>", unsafe_allow_html=True)
            if bonus_pendente > 0:
                st.markdown(f"<p style='color: #fbbf24; font-size:15px; font-style: italic; text-align:center; margin:0;'>🎁 Bônus Extras: {total_bonus_salvo} (+{bonus_pendente}) pts</p>", unsafe_allow_html=True)
            else:
                st.markdown(f"<p style='color: #fbbf24; font-size:15px; font-style: italic; text-align:center; margin:0;'>🎁 Bônus Extras: {total_bonus_salvo} pts</p>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# Inicializa o loop sincronizado definitivo
renderizar_tabuleiro_sincronizado()
