# gels-a11y-wcag-pipeline

Pipeline per **rilevare in automatico errori di accessibilità** nelle pagine web, rispetto ai
criteri **WCAG 2.2 di livello A e AA**, collegando ogni errore alla clausola corrispondente
della **EN 301 549**.

Funziona sia **prima della pubblicazione** (file HTML locali, cartelle di progetto) sia
**dopo** (URL pubblicati, sitemap, elenchi di indirizzi).

> **Cosa non fa.** Non certifica la conformità. Il controllo automatico trova solo una parte
> delle non conformità: una pagina senza errori rilevati non è per questo conforme. Lo dicono
> anche il W3C ([Evaluating Web Accessibility](https://www.w3.org/WAI/test-evaluate/)) e la
> metodologia UE di monitoraggio ([Decisione (UE) 2018/1524](https://eur-lex.europa.eu/eli/dec_impl/2018/1524)),
> che distingue il monitoraggio semplificato (automatico, per rilevare non conformità) da
> quello approfondito (per verificare la conformità).

## Riferimenti

| Riferimento | Ruolo nella pipeline |
|---|---|
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/), livelli A e AA (55 criteri) | riferimento tecnico dei controlli |
| [EN 301 549 v3.2.1](https://www.etsi.org/deliver/etsi_en/301500_301599/301549/03.02.01_60/en_301549v030201p.pdf) (basata su WCAG 2.1) | riferimento di legge oggi (norma armonizzata per WAD ed EAA; Linee guida AgID) |
| [EN 301 549 v4.1.1](https://www.etsi.org/deliver/etsi_en/301500_301599/301549/04.01.01_60/en_301549v040101p.pdf) (basata su WCAG 2.2) | pubblicata a settembre 2026, non ancora citata nella Gazzetta ufficiale UE |

Ogni errore riporta la clausola della v3.2.1 (per esempio 1.1.1 → 9.1.1.1). I sei criteri
nuovi di WCAG 2.2 (2.4.11, 2.5.7, 2.5.8, 3.2.6, 3.3.7, 3.3.8) non hanno una clausola nella
v3.2.1: i loro errori sono segnalati come **"WCAG 2.2, non ancora obbligatorio"**.
Il criterio 4.1.1 (Parsing) è escluso: è obsoleto in WCAG 2.2 e il W3C lo considera sempre
soddisfatto per HTML ([WCAG 2 FAQ](https://www.w3.org/WAI/standards-guidelines/wcag/faq/)).

## Le tre fasce di criteri

Il catalogo (`src/a11y_pipeline/data/catalog.yaml`) classifica i 55 criteri in base alle
[regole ACT](https://www.w3.org/WAI/standards-guidelines/act/rules/) del W3C e alle loro
[implementazioni negli strumenti automatici](https://www.w3.org/WAI/standards-guidelines/act/implementations/)
(situazione di novembre 2026; la classificazione è di questo progetto, non del W3C).

| Fascia | Criteri | Significato | Stato nel report se non ci sono rilevazioni |
|---|---|---|---|
| 1 | 15 | regole ACT implementate in modo coerente da strumenti automatici (solo alcuni aspetti del criterio) | nessun errore rilevato |
| 2 | 16 | regole ACT che richiedono giudizio umano o euristiche | verifica manuale necessaria |
| 3 | 24 | nessuna regola ACT | non verificabile in automatico |

Se un motore segnala qualcosa su un criterio, lo stato diventa **errori rilevati** o
**da verificare**, qualunque sia la fascia.

## Installazione

Servono Python 3.10+ e Node.js 18+ (solo per scaricare i motori JavaScript con versione fissata).

```bash
npm ci                                   # axe-core, versione fissata in package-lock.json
pip install -e ".[dev]"                  # pipeline + pytest
python -m playwright install chromium    # browser usato per i controlli
```

## Uso

```bash
# Una pagina pubblicata
a11y-check https://www.esempio.it/pagina.html

# Prima della pubblicazione: un file o un'intera cartella di HTML
a11y-check ./progetto/index.html
a11y-check ./progetto/

# Molte pagine: elenco .txt/.csv (un URL o percorso per riga) oppure sitemap
a11y-check pagine.txt
a11y-check https://www.esempio.it/sitemap.xml

# Schermo da smartphone, chiudendo prima il banner dei cookie
a11y-check https://www.esempio.it/ --viewport 320x640 --click "#accetta-cookie"

# Pagine interattive: controlla più stati (accordion aperti, finestre modali...)
a11y-check pagina.html --scenario examples/scenario_esempio.py

# Pagine protette da login: salva la sessione una volta, poi riusala
python -m playwright codegen --save-storage=storage-state.json https://piattaforma.esempio.it/login
a11y-check https://piattaforma.esempio.it/area-riservata --storage-state storage-state.json
```

Il file `storage-state.json` contiene la sessione di login: non va mai messo nella repository
(è già escluso da `.gitignore`).

Altre opzioni: `a11y-check --help`.

### Risultati

Nella cartella `a11y-report/` (modificabile con `-o`):

- `report.html`: report leggibile, in italiano, con lo stato dei 55 criteri e il dettaglio per pagina;
- `report.json`: gli stessi dati per altri programmi (pipeline, fogli di calcolo, confronti nel tempo).

Gli esiti usano il vocabolario W3C [EARL](https://www.w3.org/TR/EARL10-Schema/):
`failed` (errore) e `cantTell` (da verificare). Gli errori trovati dentro iframe di altre
origini (video incorporati, contenuti di terzi) sono segnati come `third_party` e contati a parte.

### Codice di uscita (per la CI)

| Codice | Significato |
|---|---|
| 0 | nessun errore bloccante |
| 1 | errori bloccanti trovati |
| 2 | nessuna pagina da controllare, oppure almeno una pagina non si è aperta |

Cosa è "bloccante" si sceglie con `--fail-on`:
`errori` (default: ogni errore sui contenuti propri), `errori-obbligatori` (solo i criteri
richiesti dalla EN 301 549 v3.2.1), `nessuno` (solo report).

## Test

```bash
pytest                 # unit test + test con browser su pagine di prova (circa 5 secondi)
pytest -m act          # regressione sui test case ACT del W3C (circa 6 minuti)
```

La regressione ACT scarica [`testcases.json`](https://www.w3.org/WAI/content-assets/wcag-act-rules/testcases.json)
dal W3C e, per ogni test case di una regola ACT che axe-core dichiara di implementare,
confronta l'esito con quello atteso. Fallisce se c'è un **falso positivo** (errore segnalato
su un esempio corretto). Le differenze note e motivate sono in `tests/act/known_differences.yaml`;
il riepilogo completo finisce in `reports/act-summary.json`.

Variabili d'ambiente utili:

| Variabile | Uso |
|---|---|
| `A11Y_BROWSER_CHANNEL=chrome` | usa Google Chrome installato invece del Chromium di Playwright |
| `A11Y_AXE_PATH` | percorso di un `axe.min.js` diverso da `node_modules/axe-core/axe.min.js` |
| `ACT_TESTCASES`, `ACT_BASE_URL` | copia locale dei test case ACT (per esempio da [w3c/wcag-act-rules](https://github.com/w3c/wcag-act-rules)) |
| `ACT_RULES` | limita la regressione ad alcune regole ACT (ID separati da virgola) |
| `WCAG_JSON` | copia locale di [wcag.json](https://www.w3.org/WAI/WCAG22/wcag.json) per il confronto del catalogo |

La CI (GitHub Actions, `.github/workflows/ci.yml`) esegue i test a ogni push e la
regressione ACT ogni lunedì o su richiesta.

## Struttura

```
src/a11y_pipeline/
  cli.py            riga di comando (a11y-check)
  sources.py        da URL, file, cartelle, elenchi e sitemap all'elenco di pagine
  browser.py        Playwright: apertura pagine, viewport, login, banner
  runner.py         pagine × stati × motori; caricamento degli scenari
  engines/axe.py    axe-core iniettato nella pagina e in ogni iframe (runPartial/finishRun)
  models.py         formato comune dei risultati (esiti EARL)
  catalog.py        55 criteri, fasce e clausole EN 301 549
  data/catalog.yaml catalogo
  report.py         riepilogo per criterio, report JSON e HTML
tests/              unit test, test con browser, regressione ACT
examples/           esempio di scenario
```

### Aggiungere un motore

Un motore è una classe con `name`, `version` e `scan(page, page_url, state) -> list[Finding]`
(vedi `engines/__init__.py`). Il candidato naturale è
[IBM Equal Access](https://github.com/IBMa/equal-access) (Apache-2.0), che come axe si inietta
nella pagina; poi va registrato in `get_engine()`.

### Aggiornare axe-core

1. `npm install --save-exact axe-core@<versione>`
2. `pytest` e `pytest -m act`
3. se compaiono falsi positivi, capire se sono regressioni del motore o differenze accettabili
   (in quel caso aggiungerle a `tests/act/known_differences.yaml` con la motivazione)

## Limiti noti

- Il controllo vede la pagina nello stato in cui si trova: i contenuti nascosti (accordion,
  finestre modali, schede) vanno aperti con uno scenario.
- I documenti non HTML (SVG, PDF) e le pagine che si ricaricano o cambiano indirizzo da sole
  non vengono controllati: compaiono tra le "pagine non controllate".
- axe-core segnala come errori alcuni casi che le regole ACT considerano corretti (vedi
  `tests/act/known_differences.yaml`): per esempio pulsanti con icone da font a legature.
- `target-size` (2.5.8) è l'unica regola axe per i criteri nuovi di WCAG 2.2: si può
  disattivare con `--disable-rule target-size`.

## Licenze e attribuzioni

- [axe-core](https://github.com/dequelabs/axe-core) è distribuito da Deque con licenza
  MPL-2.0; viene installato con npm e non è incluso in questa repository.
- I titoli dei criteri nel catalogo sono tratti da
  [WCAG 2.2](https://www.w3.org/TR/WCAG22/) (W3C Document License); fasce e mappatura
  EN 301 549 sono aggiunte di questo progetto.
