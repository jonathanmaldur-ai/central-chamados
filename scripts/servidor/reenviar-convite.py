#!/usr/bin/env python3
"""Reenvia o convite de criação de senha para um usuário do GLPI, pelo login (sem sudo).

    python3 ~/central-chamados/scripts/servidor/reenviar-convite.py matriz

É o mesmo e-mail do "Esqueceu sua senha?" da tela de login: vai para o e-mail cadastrado no usuário, com um link
que vale 1 dia. O e-mail precisa ser de um usuário só (o GLPI não envia se dois usuários tiverem o mesmo e-mail).
"""

import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location("configurar", Path(__file__).with_name("configurar-glpi.py"))
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: reenviar-convite.py <login>")
    login = sys.argv[1]
    chaves = cfg.ler_chaves()
    glpi = cfg.Glpi(chaves)
    try:
        usuario = next((u for u in glpi.listar("User") if u["name"].lower() == login.lower()), None)
        if usuario is None:
            raise SystemExit(f"Login \"{login}\" não existe no GLPI.")
        emails = [e["email"] for e in glpi._pedir("GET", f"/User/{usuario['id']}/UserEmail")]
        if not emails:
            raise SystemExit(f"\"{login}\" não tem e-mail cadastrado: cadastre na ficha do usuário e rode de novo.")
        email = next((e["email"] for e in glpi._pedir("GET", f"/User/{usuario['id']}/UserEmail") if e["is_default"]),
                     emails[0])
        donos = [u["name"] for u in glpi.listar("User")
                 if any(e["email"].lower() == email.lower() for e in glpi._pedir("GET", f"/User/{u['id']}/UserEmail"))]
        if len(donos) > 1:
            raise SystemExit(f"O e-mail {email} está em mais de um usuário ({', '.join(donos)}); "
                             "o GLPI não envia o convite assim. Deixe o e-mail em um só.")
    finally:
        glpi.sair()

    # Sem sessão aberta, como o "Esqueceu sua senha?" da tela de login.
    pedido = urllib.request.Request(chaves["GLPI_URL"] + "/lostPassword", method="PUT",
                                    data=json.dumps({"email": email}).encode(),
                                    headers={"App-Token": chaves["GLPI_APP_TOKEN"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, context=cfg.SSL):
            pass
    except urllib.error.HTTPError as e:
        raise SystemExit(f"O GLPI recusou: {e.code} {e.read().decode()[:200]}")
    print(f"Convite de senha reenviado para {email} (login {usuario['name']}). O link vale 1 dia; "
          "o e-mail sai em até 1 a 2 minutos.")


if __name__ == "__main__":
    main()
