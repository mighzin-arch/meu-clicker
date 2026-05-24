from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import random


app = Flask(__name__)
loja_atual = []
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jogo.db"
db = SQLAlchemy(app)

class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moedas = db.Column(db.Integer, default=0)
    pelos = db.Column(db.Integer, default=0)
    
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
    jogador = Jogador.query.get(id)
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/clicar/<int:id>", methods=["POST"])
def clicar(id):
    jogador = Jogador.query.get(id)
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
    global loja_atual
    
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
    jogador = Jogador.query.get(id)

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

@app.route("/loja", methods=["GET"])
def loja():
    global loja_atual
    if not loja_atual:
        sortear_loja()
    return jsonify(loja_atual)

@app.route("/sortear_loja", methods=["POST"])
def fazer_sorteio():
    sortear_loja()
    return jsonify(loja_atual)

@app.route("/comprar/<int:jogador_id>/<int:item_id>", methods=["POST"])
def comprar(jogador_id, item_id):
    jogador = Jogador.query.get(jogador_id)
    item = Item.query.get(item_id)

    if not item:
        return jsonify({"erro": "item inválido"}), 400

    if jogador.moedas < item.preco:
        return jsonify({"erro": "moedas insuficientes"}), 400

    jogador.moedas -= item.preco
    novo_item = Inventario(jogador_id=jogador_id, item_id=item_id)
    db.session.add(novo_item)
    db.session.commit()

    for item_loja in loja_atual:       # ← adiciona daqui
        if item_loja["id"] == item_id:
            item_loja["estoque"] -= 1
            if item_loja["estoque"] <= 0:
                item_loja["disponivel"] = False
            break                      # ← até aqui

    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})
    
@app.route("/ativar/<int:jogador_id>/<int:inventario_id>", methods=["POST"])
def ativar(jogador_id, inventario_id):
    jogador = Jogador.query.get(jogador_id)
    entrada = Inventario.query.get(inventario_id)
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
        "expira_em": entrada.expira_em.isoformat()
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
            "expira_em": entrada.expira_em.isoformat() if entrada.expira_em else None
        })
    return jsonify(resultado)

@app.route("/passivo/<int:id>", methods=["POST"])
def passivo(id):
    jogador = Jogador.query.get(id)
    
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)