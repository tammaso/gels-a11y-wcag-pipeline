"""Esempio di scenario: controlla la pagina chiusa e poi con il pannello aperto."""


def run(page, check):
    check("iniziale")
    page.click("#apri")
    check("pannello aperto")
