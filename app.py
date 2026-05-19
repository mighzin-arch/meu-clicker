from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jogo.db"
db = SQLAlchemy(app)

class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moedas = db.Column(db.Integer, default=0)
    pelos = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()
    if Jogador.query.first() is None:
        jogador = Jogador(moedas=0, pelos=0)
        db.session.add(jogador)
        db.session.commit()

@app.route("/estado", methods=["GET"])
def get_estado():
    jogador = Jogador.query.first()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/clicar", methods=["POST"])
def clicar():
    jogador = Jogador.query.first()
    jogador.pelos += 1
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})

@app.route("/vender", methods=["POST"])
def vender():
    jogador = Jogador.query.first()
    jogador.moedas += jogador.pelos
    jogador.pelos = 0
    db.session.commit()
    return jsonify({"moedas": jogador.moedas, "pelos": jogador.pelos})




pontos = 0

@app.route("/")
def index():
    return render_template("index.html")

'''@app.route("/pontos", methods=["GET"])
def get_pontos():
    return {"pontos": pontos}

@app.route("/pontos", methods=["POST"])
def set_pontos():
    global pontos
    pontos += 1
    return {"pontos": pontos}'''

if __name__ == "__main__":
    app.run(debug=True)