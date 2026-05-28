from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import random
import logging
import os

os.environ['TZ'] = 'UTC'
ultimo_sorteio = None
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
loja_atual = []
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///jogo.db")
db = SQLAlchemy(app)
sorteio_atual = 0

database_url = os.environ.get("DATABASE_URL", "sqlite:///jogo.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moedas = db.Column(db.Integer, default=0)
    pelos = db.Column(db.Integer, default=0)
    nome = db.Column(db.String, nullable=True)
    
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
    if Item.query.first() is None:
        itens = [
            Item(nome="Novelo", raridade="comum", efeito="pelo_passivo", preco=30),
            Item(nome="Erva de Gato", raridade="incomum", efeito="mais_pelos", preco=50),
            Item(nome="Laser", raridade="raro", efeito="mais_moedas", preco=150),
            Item(nome="Petisco", raridade="lendário", efeito="super_gato", preco=300)
        ]
        db.session.add_all(itens)
        db.session.commit()

@app.route("/estado/<int:id>", methods=["GET"])
def get_estado(id):
    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/clicar/<int:id>", methods=["POST"])
def clicar(id):
    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404

    pelos_por_clique = 1

    erva_ativa = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "mais_pelos"
    ).first()

    laser_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "mais_moedas"
    ).first()

    super_gato_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "super_gato"
    ).first()

    if super_gato_ativo:
        pelos_por_clique = 5
    elif erva_ativa:
        pelos_por_clique = 2


    jogador.pelos += pelos_por_clique
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

def sortear_loja():
    global loja_atual, sorteio_atual
    sorteio_atual += 1
    
    estoques = {
        "comum": (2, 4),
        "incomum": (1, 3),
        "raro": (1, 2),
        "lendário": (1, 1)
    }
    
    chances = {
        "comum": 55,
        "incomum": 25,
        "raro": 15,
        "lendário": 5
    }
    
    todos_itens = Item.query.all()
    resultado = []
    
    for item in todos_itens:
        chance = chances[item.raridade]
        disponivel = random.choices([True, False], weights=[chance, 100 - chance], k=1)[0]
        minimo, maximo = estoques[item.raridade]
        estoque = random.randint(minimo, maximo) if disponivel else 0
        resultado.append({
            "id": item.id,
            "nome": item.nome,
            "raridade": item.raridade,
            "preco": item.preco,
            "disponivel": disponivel,
            "estoque": estoque
        })
    
    loja_atual = resultado

@app.route("/vender/<int:id>", methods=["POST"])
def vender(id):
    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
        

    multiplicador = 1

    laser_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "mais_moedas"
    ).first()

    super_gato_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "super_gato"
    ).first()
    
    if super_gato_ativo:
        multiplicador = 2
    elif laser_ativo:
        multiplicador = 2

    jogador.moedas += jogador.pelos * multiplicador
    jogador.pelos = 0
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/teste")
def teste():
    return "funcionou!"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/novo_jogador", methods=["POST"])
def novo_jogador():
    jogador = Jogador()
    db.session.add(jogador)
    db.session.commit()
    return jsonify({"id": jogador.id})

@app.route("/loja/<int:jogador_id>", methods=["GET"])
def loja(jogador_id):
    global loja_atual, ultimo_sorteio
    
    agora = datetime.now()
    
    if not loja_atual or ultimo_sorteio is None:
        sortear_loja()
        ultimo_sorteio = agora
    elif (agora - ultimo_sorteio).total_seconds() >= 60:
        sortear_loja()
        ultimo_sorteio = agora
    
    proximo = ultimo_sorteio + timedelta(seconds=60)
    segundos_restantes = max(1, int((proximo - agora).total_seconds()))
    
    resultado = []
    for item in loja_atual:
        compra = CompraLoja.query.filter_by(
            jogador_id=jogador_id,
            item_id=item["id"],
            sorteio_id=sorteio_atual
        ).first()
        compras_feitas = compra.quantidade if compra else 0
        estoque_restante = item["estoque"] - compras_feitas
        resultado.append({
            **item,
            "estoque": estoque_restante,
            "disponivel": item["disponivel"] and estoque_restante > 0
        })
    
    return jsonify({
        "itens": resultado,
        "segundos_restantes": segundos_restantes
    })

@app.route("/sortear_loja", methods=["POST"])
def fazer_sorteio():
    global ultimo_sorteio
    sortear_loja()
    ultimo_sorteio = datetime.now()
    return jsonify(loja_atual)

@app.route("/comprar/<int:jogador_id>/<int:item_id>", methods=["POST"])
def comprar(jogador_id, item_id):
    jogador = db.session.get(Jogador, jogador_id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
        
    item = db.session.get(Item, item_id)

    if not item or jogador.moedas < item.preco:
        return jsonify({"erro": "Moedas insuficientes ou item inválido"}), 400

    # Pega o item da loja global para saber qual era o estoque inicial sorteado
    estoque_original = next((i for i in loja_atual if i["id"] == item_id), None)
    if not estoque_original or not estoque_original["disponivel"]:
        return jsonify({"erro": "item indisponível"}), 400

    # Verifica no BANCO DE DADOS quanto ESSE jogador já comprou
    compra = CompraLoja.query.filter_by(
        jogador_id=jogador_id,
        item_id=item_id,
        sorteio_id=sorteio_atual
    ).first()

    compras_feitas = compra.quantidade if compra else 0

    if compras_feitas >= estoque_original["estoque"]:
        return jsonify({"erro": "Você já esgotou seu estoque deste item"}), 400

    # Registra a compra no banco
    if compra:
        compra.quantidade += 1
    else:
        nova_compra = CompraLoja(jogador_id=jogador_id, item_id=item_id, sorteio_id=sorteio_atual, quantidade=1)
        db.session.add(nova_compra)

    # Cria o item no inventário
    jogador.moedas -= item.preco
    novo_item = Inventario(jogador_id=jogador_id, item_id=item_id)
    db.session.add(novo_item)
    
    db.session.commit()

    # IMPORTANTE: Não mexemos na variável 'loja_atual' aqui!
    # O estoque de cada um é controlado pela tabela CompraLoja.

    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/ativar/<int:jogador_id>/<int:inventario_id>", methods=["POST"])
def ativar(jogador_id, inventario_id):
    jogador = db.session.get(Jogador, jogador_id)
    entrada = db.session.get(Inventario, inventario_id)
    item = Item.query.get(entrada.item_id)

    if entrada.equipado:
        return jsonify({"erro": "item já ativo"}), 400

    duracoes = {
        "pelo_passivo": 60,
        "mais_pelos": 180,
        "mais_moedas": 120,
        "super_gato": 300
    }

    duracao = duracoes.get(item.efeito, 60)
    entrada.equipado = True
    entrada.expira_em = datetime.now() + timedelta(seconds=duracao)

    if item.efeito == "super_gato":
        jogador.pelos += 20

    db.session.commit()

    return jsonify({
        "moedas": jogador.moedas,
        "pelos": jogador.pelos,
        "efeito": item.efeito,
        "expira_em": entrada.expira_em.isoformat() + "Z"
    })

@app.route("/inventario/<int:jogador_id>", methods=["GET"])
def inventario(jogador_id):
    entradas = Inventario.query.filter_by(jogador_id=jogador_id).all()
    resultado = []
    for entrada in entradas:
        item = Item.query.get(entrada.item_id)

        if entrada.equipado and entrada.expira_em and entrada.expira_em < datetime.now():
            db.session.delete(entrada)
            db.session.commit()
            continue

        ativo = entrada.equipado and entrada.expira_em and entrada.expira_em > datetime.now()
        resultado.append({
            "inventario_id": entrada.id,
            "nome": item.nome,
            "efeito": item.efeito,
            "equipado": ativo,
            "expira_em": entrada.expira_em.isoformat() + "Z" if entrada.expira_em else None
        })
    return jsonify(resultado)

@app.route("/passivo/<int:id>", methods=["POST"])
def passivo(id):
    jogador = db.session.get(Jogador, id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
        
    
    pelos_passivos = 0

    novelo_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "pelo_passivo"
    ).first()

    laser_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "mais_moedas"
    ).first()

    super_gato_ativo = Inventario.query.join(Item).filter(
        Inventario.jogador_id == id,
        Inventario.equipado == True,
        Inventario.expira_em > datetime.now(),
        Item.efeito == "super_gato"
    ).first()

    if novelo_ativo:
        pelos_passivos += 1
    if laser_ativo:
        pelos_passivos += 2
    if super_gato_ativo:
        pelos_passivos += 1

    jogador.pelos += pelos_passivos
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})


@app.route("/nome/<int:jogador_id>", methods=["POST"])
def salvar_nome(jogador_id):
    jogador = db.session.get(Jogador, jogador_id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
    
    dados = request.get_json()
    nome = dados.get("nome", "").strip()
    
    if not nome:
        return jsonify({"erro": "nome inválido"}), 400
    
    if len(nome) > 20:
        return jsonify({"erro": "nome muito longo"}), 400
    
    jogador.nome = nome
    db.session.commit()
    return jsonify({"nome": jogador.nome})

@app.route("/ranking", methods=["GET"])
def ranking():
    jogadores = Jogador.query.filter(
        Jogador.nome != None
    ).order_by(Jogador.moedas.desc()).limit(10).all()
    
    resultado = []
    for i, jogador in enumerate(jogadores):
        resultado.append({
            "posicao": i + 1,
            "nome": jogador.nome,
            "moedas": jogador.moedas
        })
    
    return jsonify(resultado)

@app.route("/nome/<int:jogador_id>", methods=["GET"])
def get_nome(jogador_id):
    jogador = db.session.get(Jogador, jogador_id)
    if not jogador:
        return jsonify({"erro": "jogador não encontrado"}), 404
    return jsonify({"nome": jogador.nome})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)