import argparse
import os
import shutil
from pathlib import Path


def _obter_automacao():
    from modules.vpn_automation import RadminAutomation

    return RadminAutomation()


def cmd_janelas(_args):
    from pywinauto import Desktop

    encontradas = False

    for janela in Desktop(backend="uia").windows(visible_only=True):
        try:
            titulo = janela.window_text().strip()

            if "radmin" not in titulo.casefold():
                continue

            info = janela.element_info
            retangulo = janela.rectangle()

            print(f"titulo={titulo!r}")
            print(f"classe={info.class_name!r}")
            print(f"visivel={janela.is_visible()}")
            print(f"tamanho={retangulo.width()}x{retangulo.height()}")
            print()

            encontradas = True

        except Exception:
            continue

    if not encontradas:
        print("Nenhuma janela do Radmin VPN foi encontrada.")


def cmd_programa(_args):
    automacao = _obter_automacao()

    if automacao.localizar_janela():
        print("Janela principal do Radmin VPN localizada.")
        return

    print("Radmin VPN não localizado.")
    print("A abertura automática não está implementada.")
    print("Abra o Radmin VPN manualmente e execute este diagnóstico novamente.")


def cmd_formulario(_args):
    automacao = _obter_automacao()

    if not automacao.localizar_janela():
        print("Janela principal não localizada. Abra o Radmin VPN manualmente.")
        return

    if not automacao.localizar_formulario():
        print("Formulário de conexão não localizado.")
        return

    info = automacao.formulario.element_info

    print("Formulário de conexão localizado.")
    print(f"classe={info.class_name!r}")
    print(f"automation_id={info.automation_id!r}")


def cmd_campos(_args):
    automacao = _obter_automacao()

    if not automacao.localizar_janela():
        print("Janela principal não localizada. Abra o Radmin VPN manualmente.")
        return

    if not automacao.localizar_formulario():
        print("Formulário de conexão não localizado.")
        return

    encontrados = False

    for elemento in automacao.formulario.descendants():
        try:
            info = elemento.element_info
            campo = info.automation_id.rsplit(".", 1)[-1]

            if campo not in {"LENetName", "LEPassword"}:
                continue

            print(f"campo={campo}")
            print(f"classe={info.class_name!r}")
            print(f"controle={info.control_type!r}")
            print(f"automation_id={info.automation_id!r}")
            print()

            encontrados = True

        except Exception:
            continue

    if not encontrados:
        print("Campos LENetName e LEPassword não foram encontrados.")


def cmd_guia_preenchimento(_args):
    print("1. Abra o Radmin VPN manualmente.")
    print("2. Localize a janela principal e o formulário de conexão.")
    print("3. Confira o nome da rede antes de preencher.")
    print("4. Preencha os campos manualmente, sem registrar senhas.")
    print("5. Não execute este diagnóstico durante uma conexão real.")


def cmd_guia_conexao(_args):
    print("1. Confira o nome exibido no campo da rede.")
    print("2. Envie a solicitação manualmente.")
    print("3. Observe o estado real na janela principal.")
    print("4. Não presuma sucesso sem evidência de estado da rede.")
    print("5. Não desconecte nem altere outras redes.")


def cmd_ocr(args):
    imagem = Path(args.imagem) if args.imagem else Path("assets/formulario_radmin.bmp")

    if not imagem.is_file():
        print(f"OCR ignorado: imagem não encontrada: {imagem}")
        return

    tesseract = os.environ.get("RADMIN_TESSERACT_CMD") or shutil.which("tesseract")

    if not tesseract:
        print("OCR ignorado: Tesseract não encontrado no PATH.")
        return

    try:
        import pytesseract
        from PIL import Image

    except ImportError:
        print("OCR ignorado: pytesseract ou Pillow não instalados.")
        return

    pytesseract.pytesseract.tesseract_cmd = tesseract
    idioma = os.environ.get("RADMIN_OCR_LANG", "por")

    try:
        texto = pytesseract.image_to_string(
            Image.open(imagem),
            lang=idioma
        )

    except Exception as exc:
        print(f"OCR ignorado: {exc}")
        return

    print(texto.strip() or "Nenhum texto reconhecido.")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnósticos manuais e somente leitura do Radmin VPN."
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    subcomandos.add_parser(
        "janelas",
        help="Lista janelas do Radmin sem mostrar identificadores voláteis."
    ).set_defaults(func=cmd_janelas)

    subcomandos.add_parser(
        "programa",
        help="Verifica apenas se a janela do Radmin pode ser localizada."
    ).set_defaults(func=cmd_programa)

    subcomandos.add_parser(
        "formulario",
        help="Localiza o diálogo de conexão sem clicar."
    ).set_defaults(func=cmd_formulario)

    subcomandos.add_parser(
        "campos",
        help="Inspeciona os campos do formulário sem ler senhas."
    ).set_defaults(func=cmd_campos)

    subcomandos.add_parser(
        "guia-preenchimento",
        help="Mostra o checklist manual de preenchimento."
    ).set_defaults(func=cmd_guia_preenchimento)

    subcomandos.add_parser(
        "guia-conexao",
        help="Mostra o checklist manual de envio e observação do resultado."
    ).set_defaults(func=cmd_guia_conexao)

    ocr = subcomandos.add_parser(
        "ocr",
        help="Reconhece texto de uma imagem usando OCR opcional."
    )
    ocr.add_argument("--imagem", default=None)
    ocr.set_defaults(func=cmd_ocr)

    args = parser.parse_args()

    try:
        args.func(args)

    except Exception as exc:
        print(f"Diagnóstico indisponível: {exc}")


if __name__ == "__main__":
    main()
