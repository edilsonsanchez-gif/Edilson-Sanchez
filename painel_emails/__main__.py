"""Linha de comando: python -m painel_emails <comando>"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

from . import banco, coletor, config, servidor
from .classificador import Classificador

EXEMPLOS = [
    ("Loja Virtual", "vendas@loja.com.br", "Nova venda realizada - Pedido #{n}",
     "Você vendeu 1x Kit Premium. Pagamento aprovado via Pix. Valor: R$ 189,90."),
    ("Mercado Pago", "noreply@mercadopago.com", "Você recebeu um pagamento de R$ {v}",
     "Pagamento recebido referente ao pedido {n}."),
    ("Ana Souza", "ana.souza@gmail.com", "Dúvida sobre tamanho",
     "Olá! Gostaria de saber se o modelo M serve para quem veste 40. Vocês entregam em Curitiba?"),
    ("Carlos Lima", "carlos.lima@hotmail.com", "Orçamento para 20 unidades",
     "Bom dia, qual o valor para 20 unidades e qual o prazo de entrega?"),
    ("Juliana Reis", "juliana.reis@outlook.com", "Produto chegou!",
     "Recebi o produto hoje, muito obrigada! Ficou perfeito."),
    ("Pedro Alves", "pedro.alves@gmail.com", "Não recebi meu pedido",
     "Fiz a compra há 10 dias e não recebi. Preciso de um retorno, por favor."),
    ("Marina Costa", "marina@empresa.com", "Parceria",
     "Olá, tudo bem? Acompanho o trabalho de vocês e adoraria conversar sobre uma parceria."),
    ("Newsletter Shop", "news@marketing.com", "Ofertas da semana",
     "Confira nossas ofertas. Para descadastrar clique aqui."),
]


def demo(caminho: Path) -> None:
    caminho.unlink(missing_ok=True)
    con = banco.conectar(caminho)
    cls = Classificador()
    rnd = random.Random(7)
    agora = datetime.now().astimezone()
    uid = 0
    for dias_atras in range(30):
        for _ in range(rnd.randint(1, 7)):
            nome, end, assunto, corpo = rnd.choice(EXEMPLOS)
            uid += 1
            n, v = rnd.randint(1000, 9999), f"{rnd.randint(40, 600)},90"
            assunto, corpo = assunto.format(n=n, v=v), corpo.format(n=n, v=v)
            res = cls.classificar(assunto, corpo, end)
            quando = agora - timedelta(days=dias_atras, minutes=rnd.randint(0, 600))
            banco.inserir_email(con, {
                "pasta": "INBOX", "uidvalidity": 1, "uid": uid, "gm_msgid": None,
                "message_id": f"<demo-{uid}@exemplo>", "remetente": nome, "remetente_email": end,
                "assunto": assunto, "data": quando.isoformat(timespec="seconds"),
                "trecho": corpo[:240], "corpo": corpo, "categoria": res.categoria,
                "motivos": "\n".join(res.motivos),
            })
    banco.gravar_estado(con, "ultima_sincronizacao", agora.isoformat(timespec="seconds"))
    con.commit()
    con.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m painel_emails", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sincronizar", help="busca e-mails novos no Gmail e classifica")
    s = sub.add_parser("painel", help="abre o painel web")
    s.add_argument("--sincronizar", action="store_true", help="busca e-mails antes de abrir")
    s.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 para acessar de outro aparelho da rede")
    sub.add_parser("reclassificar", help="reaplica regras.json a todos os e-mails salvos")
    sub.add_parser("demo", help="abre o painel com dados de exemplo (sem Gmail)")
    args = p.parse_args()

    cfg = config.carregar()
    if args.cmd == "demo":
        cfg.banco = config.RAIZ / "emails-demo.db"
        demo(cfg.banco)
        servidor.servir(cfg, demo=True)
    elif args.cmd == "sincronizar":
        con = banco.conectar(cfg.banco)
        coletor.sincronizar(cfg, con)
        con.close()
    elif args.cmd == "reclassificar":
        con = banco.conectar(cfg.banco)
        print(f"{banco.reclassificar_tudo(con, Classificador())} e-mail(s) reclassificados.")
        con.close()
    else:
        if args.sincronizar:
            con = banco.conectar(cfg.banco)
            coletor.sincronizar(cfg, con)
            con.close()
        servidor.servir(cfg, host=args.host)


if __name__ == "__main__":
    main()
