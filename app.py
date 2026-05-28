from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random
import logging
import os

app = Flask(__name__)

# Silencia logs desnecessários no terminal
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
database_url = os.environ.get("DATABASE_URL", "sqlite:///jogo.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Variáveis Globais
loja_atual = []
ultimo_sorteio = None
sorteio_atual = 0

# --- MODELOS ---
class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moedas = db.Column(db.Integer, default=0)
    pelos = db.Column(db.Integer, default=0)
    nome = db.Column(db.String(20), nullable=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String, nullable=False)
    raridade = db.Column(db.String, nullable=False)
    efeito = db.Column(db.String, nullable=False)
    preco = db.Column(db.Integer, nullable=False)

class Inventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey("jogador.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    equipado = db.Column(db.Boolean, default=False)
    expira_em = db.Column(db.DateTime, nullable=True)

class CompraLoja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey("jogador.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    sorteio_id = db.Column(db.Integer, nullable=False)

with app.app_context():
    db.create_all()
    if db.session.query(Item).first() is None:
        itens_iniciais = [
            Item(nome="Novelo", raridade="comum", efeito="pelo_passivo", preco=30),
            Item(nome="Erva de Gato", raridade="incomum", efeito="mais_pelos", preco=50),
            Item(nome="Laser", raridade="raro", efeito="mais_moedas", preco=150),
            Item(nome="Petisco", raridade="lendário", efeito="super_gato", preco=300)
        ]
        db.session.add_all(itens_iniciais)
        db.session.commit()

# --- ROTAS PRINCIPAIS ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/novo_jogador", methods=["POST"])
def novo_jogador():
    jogador = Jogador()
    db.session.add(jogador)
    db.session.commit()
    return jsonify({"id": jogador.id})

@app.route("/estado/<int:id>")
def get_estado(id):
    jogador = db.session.get(Jogador, id)
    if not jogador: return jsonify({"erro": "Não encontrado"}), 404
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/clicar/<int:id>", methods=["POST"])
def clicar(id):
    jogador = db.session.get(Jogador, id)
    if not jogador: return jsonify({"erro": "Não encontrado"}), 404
    
    pelos_por_clique = 1
    agora = datetime.now() # Mantido seu padrão de horário
    
    super_gato = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito == "super_gato").first()
    erva = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito == "mais_pelos").first()

    if super_gato: pelos_por_clique = 5
    elif erva: pelos_por_clique = 2

    jogador.pelos += pelos_por_clique
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/vender/<int:id>", methods=["POST"])
def vender(id):
    jogador = db.session.get(Jogador, id)
    if not jogador: return jsonify({"erro": "Não encontrado"}), 404
    
    multiplicador = 1
    agora = datetime.now()
    buff = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito.in_(["mais_moedas", "super_gato"])).first()
    
    if buff: multiplicador = 2

    jogador.moedas += (jogador.pelos * multiplicador)
    jogador.pelos = 0
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

# --- SISTEMA DE LOJA ---

def sortear_loja():
    global loja_atual, sorteio_atual
    sorteio_atual += 1
    estoques = {"comum": (2, 4), "incomum": (1, 3), "raro": (1, 2), "lendário": (1, 1)}
    chances = {"comum": 55, "incomum": 25, "raro": 15, "lendário": 5}
    
    todos = Item.query.all()
    resultado = []
    for item in todos:
        disp = random.choices([True, False], weights=[chances[item.raridade], 100-chances[item.raridade]])[0]
        est = random.randint(*estoques[item.raridade]) if disp else 0
        resultado.append({"id": item.id, "nome": item.nome, "raridade": item.raridade, "preco": item.preco, "disponivel": disp, "estoque": est})
    loja_atual = resultado

@app.route("/loja/<int:jogador_id>")
def get_loja(jogador_id):
    global loja_atual, ultimo_sorteio
    agora = datetime.now()
    
    if not loja_atual or ultimo_sorteio is None or (agora - ultimo_sorteio).total_seconds() >= 60:
        sortear_loja()
        ultimo_sorteio = agora
    
    segundos_restantes = max(1, int((ultimo_sorteio + timedelta(seconds=60) - agora).total_seconds()))
    
    resultado = []
    for item in loja_atual:
        compra = CompraLoja.query.filter_by(jogador_id=jogador_id, item_id=item["id"], sorteio_id=sorteio_atual).first()
        restante = item["estoque"] - (compra.quantidade if compra else 0)
        resultado.append({**item, "estoque": restante, "disponivel": item["disponivel"] and restante > 0})
    
    return jsonify({"itens": resultado, "segundos_restantes": segundos_restantes})

@app.route("/comprar/<int:jogador_id>/<int:item_id>", methods=["POST"])
def comprar(jogador_id, item_id):
    jogador = db.session.get(Jogador, jogador_id)
    item = db.session.get(Item, item_id)
    if not jogador or not item or jogador.moedas < item.preco:
        return jsonify({"erro": "Saldo insuficiente"}), 400

    item_loja = next((i for i in loja_atual if i["id"] == item_id), None)
    if not item_loja or not item_loja["disponivel"]:
        return jsonify({"erro": "Esgotado"}), 400

    compra = CompraLoja.query.filter_by(jogador_id=jogador_id, item_id=item_id, sorteio_id=sorteio_atual).first()
    if compra and compra.quantidade >= item_loja["estoque"]:
        return jsonify({"erro": "Limite atingido"}), 400

    if compra: compra.quantidade += 1
    else: db.session.add(CompraLoja(jogador_id=jogador_id, item_id=item_id, sorteio_id=sorteio_atual, quantidade=1))

    jogador.moedas -= item.preco
    db.session.add(Inventario(jogador_id=jogador_id, item_id=item_id))
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

# --- INVENTÁRIO E RANKING ---

@app.route("/inventario/<int:jogador_id>")
def get_inventario(jogador_id):
    entradas = Inventario.query.filter_by(jogador_id=jogador_id).all()
    agora = datetime.now()
    res = []
    for e in entradas:
        item = db.session.get(Item, e.item_id)
        # Limpeza de itens expirados
        if e.equipado and e.expira_em and e.expira_em < agora:
            db.session.delete(e)
            continue
        res.append({
            "inventario_id": e.id, "nome": item.nome, "efeito": item.efeito,
            "equipado": (e.equipado and e.expira_em > agora) if e.expira_em else False,
            "expira_em": e.expira_em.isoformat() + "Z" if e.expira_em else None
        })
    db.session.commit()
    return jsonify(res)

@app.route("/ativar/<int:jogador_id>/<int:inventario_id>", methods=["POST"])
def ativar(jogador_id, inventario_id):
    entrada = db.session.get(Inventario, inventario_id)
    if not entrada or entrada.equipado: return jsonify({"erro": "Erro ao ativar"}), 400
    
    item = db.session.get(Item, entrada.item_id)
    duracoes = {"pelo_passivo": 60, "mais_pelos": 180, "mais_moedas": 120, "super_gato": 300}
    
    entrada.equipado = True
    entrada.expira_em = datetime.now() + timedelta(seconds=duracoes.get(item.efeito, 60))
    
    if item.efeito == "super_gato":
        jogador = db.session.get(Jogador, jogador_id)
        jogador.pelos += 20
        
    db.session.commit()
    return jsonify({"sucesso": True, "expira_em": entrada.expira_em.isoformat() + "Z"})

@app.route("/passivo/<int:id>", methods=["POST"])
def passivo(id):
    jogador = db.session.get(Jogador, id)
    if not jogador: return jsonify({"erro": "Não encontrado"}), 404
    agora = datetime.now()
    pelos_p = 0
    # Verifica buffs passivos
    n = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito == "pelo_passivo").first()
    l = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito == "mais_moedas").first()
    s = Inventario.query.join(Item).filter(Inventario.jogador_id == id, Inventario.equipado == True, Inventario.expira_em > agora, Item.efeito == "super_gato").first()
    if n: pelos_p += 1
    if l: pelos_p += 2
    if s: pelos_p += 1
    jogador.pelos += pelos_p
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/nome/<int:jogador_id>", methods=["GET", "POST"])
def gerenciar_nome(jogador_id):
    jogador = db.session.get(Jogador, jogador_id)
    if not jogador: return jsonify({"erro": "Não encontrado"}), 404
    if request.method == "POST":
        dados = request.get_json()
        nome = dados.get("nome", "").strip()
        if not nome or len(nome) > 20: return jsonify({"erro": "Nome inválido"}), 400
        jogador.nome = nome
        db.session.commit()
        return jsonify({"nome": jogador.nome})
    return jsonify({"nome": jogador.nome})

@app.route("/ranking")
def ranking():
    top = Jogador.query.filter(Jogador.nome != None).order_by(Jogador.moedas.desc()).limit(10).all()
    return jsonify([{"posicao": i+1, "nome": j.nome, "moedas": j.moedas} for i, j in enumerate(top)])

if __name__ == "__main__":
    # Importante: o Railway define a porta sozinho
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)