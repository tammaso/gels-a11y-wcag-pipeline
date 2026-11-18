"""Esempio di scenario: controllare più stati di una pagina interattiva.

Uso:
    a11y-check pagina.html --scenario examples/scenario_esempio.py

La funzione run riceve la pagina Playwright e la funzione check(etichetta):
chiama check() ogni volta che la pagina è in uno stato da controllare.
Documentazione di Playwright per Python: https://playwright.dev/python/docs/api/class-page
"""


def run(page, check):
    # 1. Stato iniziale, così come si apre la pagina
    check("iniziale")

    # 2. Apre tutti i pannelli di un accordion (adattare il selettore alla pagina)
    # (element_handles: l'elenco resta fisso anche quando aria-expanded cambia dopo il clic)
    buttons = page.locator("button[aria-expanded='false']").element_handles()
    for button in buttons:
        button.click()
    if buttons:
        check("accordion aperti")

    # 3. Apre una finestra modale, se presente
    opener = page.locator("[data-a11y-open-modal]").first
    if opener.count():
        opener.click()
        check("finestra modale aperta")
