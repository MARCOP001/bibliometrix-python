# Patch notes: funzioni testabili da Biblioshiny

Questo documento riassume le modifiche rimaste nel progetto dopo la pulizia.
Gli script esterni, i test smoke e gli output HTML/CSV sono stati rimossi perche'
la dimostrazione del funzionamento avviene direttamente dalla dashboard
Biblioshiny.

## Obiettivo

La pipeline ETL deve produrre un DataFrame standardizzato compatibile con le
funzioni in `functions/`. Le funzioni patchate devono quindi:

- accettare il valore reattivo usato da Biblioshiny;
- continuare ad accettare anche un normale `pd.DataFrame`;
- fallire con messaggi chiari se mancano colonne obbligatorie;
- non rompersi su valori vuoti o tipi numerici arrivati come stringhe.

## Modifica comune

Le funzioni patchate usano un helper simile a:

```python
_resolve_dataframe(df)
```

Questo serve per supportare entrambi gli input:

```python
get_funzione(df_pandas)
get_funzione(df_shiny_reactive)
```

Il problema della versione precedente era spesso questo:

```python
df.get()
```

Dentro Shiny poteva funzionare, ma su un `pd.DataFrame` diretto chiamava il
metodo `DataFrame.get()`, che ha un significato diverso e richiede una chiave.

## Funzioni patchate

### `get_annual_production`

Sezione Biblioshiny:

```text
Overview -> Annual Scientific Production
```

Usa la colonna `PY`. La patch valida la presenza di `PY`, converte gli anni in
valori numerici e ignora anni non validi.

### `get_average_citations`

Sezione Biblioshiny:

```text
Overview -> Average Citations per Year
```

Usa `PY` e `TC`. La patch converte entrambe le colonne in valori numerici prima
dei calcoli.

### `get_relevant_sources`

Sezione Biblioshiny:

```text
Sources -> Most Relevant Sources
```

Richiede `Run Analysis`. Usa `SO` e conta quante volte compare ogni fonte.
La patch elimina fonti vuote e segnala chiaramente se `SO` manca.

### `get_bradford_law`

Sezione Biblioshiny:

```text
Sources -> Bradford's Law
```

Usa `SO` per ordinare le fonti e dividerle nelle zone di Bradford. La patch
rende piu' robusti i casi con dataset piccoli o poche fonti.

### `get_relevant_authors`

Sezione Biblioshiny:

```text
Authors -> Most Relevant Authors
```

Richiede `Run Analysis`. Usa `AU`, che deve essere una lista di autori. La patch
normalizza il parametro di frequenza della dashboard e corregge il conteggio
frazionato.

### `get_lotka_law`

Sezione Biblioshiny:

```text
Authors -> Lotka's Law
```

Usa `AU` per calcolare la distribuzione della produttivita' degli autori. La
patch gestisce anche dataset con un solo livello di produttivita'.

### `get_cited_documents`

Sezione Biblioshiny:

```text
Documents -> Most Global Cited Documents
```

Richiede `Run Analysis`. Usa `SR`, `DI`, `TC` e `PY`. La patch usa `SR` gia'
prodotto dalla standardizzazione, valida la misura scelta dalla dashboard e
gestisce anni con media citazioni pari a zero.

## Correzione dashboard

In `app.py` molte tabelle usavano:

```python
DT(table, style="width=100%;")
```

Questa non e' sintassi CSS valida e poteva generare errori come:

```text
Error: not enough values to unpack (expected 2, got 1)
```

La correzione applicata e':

```python
DT(table, style="width:100%;")
```

## Artefatti rimossi

Sono stati rimossi:

- `scripts/`;
- `tests/`;
- `analysis_results/`.

Questi file servivano solo per testare e visualizzare le funzioni fuori da
Biblioshiny. Non sono necessari per mostrare il funzionamento dalla dashboard.
