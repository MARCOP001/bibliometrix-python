# Patch notes: test e uso reale delle funzioni Bibliometrix

Questo documento riassume le modifiche fatte rispetto alla versione precedente,
con lo scopo di spiegare cosa e' stato cambiato e perche'.

## Obiettivo generale

La richiesta della traccia e' verificare che il DataFrame standardizzato dalla
pipeline ETL possa essere passato ad alcune funzioni della cartella `functions/`.
Se una funzione fallisce nonostante il DataFrame sia coerente con lo schema
Bibliometrix, la funzione va corretta con una patch minima.

Le modifiche seguono questa logica:

1. partire da un file grezzo;
2. applicare la pipeline ETL (`extract_from_file` -> `convert2df`);
3. verificare che il DataFrame standardizzato rispetti il contratto della traccia;
4. passare il DataFrame standardizzato alle funzioni analitiche;
5. correggere solo cio' che impedisce l'uso corretto delle funzioni;
6. mantenere compatibilita' con la Shiny dashboard;
7. produrre risultati reali analizzabili, non solo test automatici.

## `functions/get_annualproduction.py`

### Cosa non andava nella vecchia funzione

La vecchia funzione non era necessariamente sbagliata quando veniva usata dentro
Biblioshiny, ma era fragile per l'uso richiesto dalla traccia.

Il problema principale era questa riga:

```python
data = df.get()
```

Questa riga assumeva che `df` fosse sempre il valore reattivo della dashboard
Shiny. In Shiny questa assunzione puo' funzionare, perche' `df` e' un oggetto
che espone un metodo `.get()` senza argomenti.

Fuori dalla dashboard, pero', il risultato della pipeline ETL e' normalmente un
`pd.DataFrame`. Anche `pd.DataFrame` ha un metodo `.get()`, ma e' un metodo
diverso: richiede una chiave, ad esempio `dataframe.get("PY")`.

Quindi chiamare la funzione cosi':

```python
get_annual_production(dataframe_standardizzato)
```

poteva generare un errore come:

```text
TypeError: NDFrame.get() missing 1 required positional argument: 'key'
```

Il secondo problema era l'import globale:

```python
from www.services import *
```

Per calcolare la produzione annuale servono solo `pandas` e `plotly`, ma
quell'import trascinava dentro molte altre dipendenze del progetto. Durante il
test isolato questo poteva far fallire la funzione per motivi non collegati alla
funzione stessa, ad esempio una dipendenza usata da altre analisi.

Il terzo punto era la gestione della colonna `PY`: la vecchia funzione assumeva
che gli anni fossero gia' puliti e numerici. Se dalla pipeline arrivavano stringhe
come `"2020"`, valori vuoti o valori non convertibili, il calcolo poteva rompersi
o produrre risultati poco affidabili.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `pandas`;
  - `plotly.express`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta la funzione helper `_annual_publications_table(data)`.
- La funzione `get_annual_production(df)` ora usa questi helper prima di creare
  il grafico.

### Perche'

La versione originale faceva direttamente:

```python
data = df.get()
```

Questo funzionava nella Shiny dashboard, dove `df` e' un oggetto reattivo, ma
non funzionava bene nei test o negli script esterni quando si passava un normale
`pd.DataFrame`.

La patch permette entrambi gli usi:

```python
get_annual_production(df_pandas)
get_annual_production(df_shiny_reactive)
```

Inoltre, `_annual_publications_table(data)` rende piu' robusta la gestione della
colonna `PY`:

- verifica che `PY` esista;
- converte gli anni in numeri;
- ignora anni non validi;
- riempie gli anni mancanti con frequenza `0`.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_annual_production(df)
```

Il valore restituito non e' cambiato:

```python
return fig, publications_per_year
```

Quindi la chiamata gia' presente in `app.py` continua a funzionare.

## `functions/get_averagecitations.py`

### Cosa non andava nella vecchia funzione

La vecchia funzione aveva la stessa fragilita' di input:

```python
data = df.get()
```

Quindi era comoda dentro Shiny, ma fragile quando si voleva passare direttamente
il `pd.DataFrame` prodotto dalla pipeline ETL.

In piu', questa funzione usa due colonne importanti del contratto:

- `PY`, publication year;
- `TC`, total citations.

La vecchia funzione assumeva che entrambe fossero gia' numeriche e pronte per i
calcoli:

```python
table["MeanTCperYear"] = round(table["MeanTCperArt"] / (current_year - table["PY"]), 2)
```

Se `PY` arrivava come stringa, ad esempio `"2024"`, l'operazione
`current_year - table["PY"]` poteva fallire. Questo e' rilevante per la traccia
perche' la pipeline ETL deve standardizzare i dati, ma le funzioni analitiche
devono comunque essere robuste rispetto ai tipi effettivamente ricevuti.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `pandas`;
  - `plotly.express`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta validazione minima delle colonne `PY` e `TC`.
- Convertite `PY` e `TC` con `pd.to_numeric`.
- Filtrate le righe senza anno valido.

### Perche'

La patch consente alla funzione di accettare:

```python
get_average_citations(df_pandas)
get_average_citations(df_shiny_reactive)
```

e verifica che gli output della standardizzazione siano effettivamente adatti ai
calcoli bibliometrici sulle citazioni.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_average_citations(df)
```

Il valore restituito non e' cambiato:

```python
return fig, table
```

Quindi la sezione Biblioshiny:

```text
Overview -> Average Citations per Year
```

dovrebbe continuare a funzionare senza modifiche lato `app.py`.

## `functions/get_citeddocuments.py`

### Cosa non andava nella vecchia funzione

La vecchia funzione era piu' difficile da testare fuori da Biblioshiny per tre
motivi principali.

Prima di tutto dipendeva da import globali:

```python
from www.services import *
```

e ricostruiva il tag `SR` dentro la funzione tramite `metaTagExtraction`.
Questo e' comodo in un flusso Shiny gia' pronto, ma per la traccia e' meno
adatto: se vogliamo verificare che la pipeline ETL standardizzi davvero `SR`,
la funzione non deve mascherare il problema ricalcolandolo internamente.

Il secondo problema era di nuovo l'assunzione:

```python
df = df.get()
```

che funziona con un valore reattivo Shiny, ma non con un normale
`pd.DataFrame` passato direttamente da uno script o da un test.

Infine, la funzione assumeva che `PY` e `TC` fossero gia' numerici e che la
media delle citazioni per anno fosse sempre maggiore di zero. Su dataset molto
recenti, come quello Scopus usato qui, molti documenti hanno `TC = 0`: questo
poteva rendere fragile il calcolo di `NormalizedTC` e la dimensione dei marker
nel grafico.

### Cosa e' stato modificato

- Sostituito l'import globale con import espliciti:
  - `pandas`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Rimossa la dipendenza da `metaTagExtraction`: ora la funzione usa `SR`
  direttamente dal DataFrame standardizzato.
- Aggiunta validazione minima delle colonne `SR`, `DI`, `TC`, `PY`.
- Convertite `PY` e `TC` in valori numerici prima dei calcoli.
- Aggiunta validazione del parametro `cited_docs_measure`.
- Reso robusto `NormalizedTC` quando un anno ha media citazioni pari a zero.
- Reso robusto il plot quando tutti i valori della metrica sono pari a zero.

### Perche'

La patch consente alla funzione di accettare:

```python
get_cited_documents(df_pandas, 10, "total_cit")
get_cited_documents(df_shiny_reactive, 10, "total_cit")
```

e allo stesso tempo verifica che la standardizzazione abbia prodotto davvero le
colonne necessarie per l'analisi dei documenti citati.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_cited_documents(df, num_of_cited_docs, cited_docs_measure)
```

Il valore restituito non e' cambiato:

```python
return fig, table
```

Questa funzione e' facilmente verificabile in Biblioshiny dalla sezione:

```text
Documents -> Most Global Cited Documents
```

Anche qui bisogna cliccare `Run Analysis` prima di vedere plot e tabella.

## `functions/get_relevantsources.py`

### Cosa non andava nella vecchia funzione

Anche questa funzione era legata al contesto Shiny per lo stesso motivo:

```python
data = df.get()
```

Quindi funzionava quando `df` era il contenitore reattivo della dashboard, ma non
era comoda da usare direttamente con il `pd.DataFrame` prodotto dalla pipeline
ETL.

Inoltre la vecchia funzione assumeva che la colonna `SO` fosse sempre presente e
utilizzabile:

```python
data = data.dropna(subset=["SO"])
source_counts = data["SO"].value_counts().reset_index()
```

Se il DataFrame standardizzato non aveva `SO`, oppure se `SO` conteneva solo
valori vuoti, l'errore non era esplicito. La patch aggiunge controlli minimi per
far fallire la funzione con un messaggio chiaro quando manca la colonna richiesta.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `pandas`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta validazione minima della colonna `SO`.
- Filtrate le fonti vuote.
- Aggiunto `.copy()` dopo `head(num_of_sources)` per evitare un warning Pandas.

### Perche'

Anche questa funzione originale assumeva che l'input fosse sempre un oggetto con
`.get()`, quindi era fragile fuori dalla dashboard.

La patch consente alla funzione di accettare:

```python
get_relevant_sources(df_pandas, 10)
get_relevant_sources(df_shiny_reactive, 10)
```

La validazione su `SO` serve per fallire in modo chiaro se il DataFrame non ha la
colonna richiesta per calcolare le fonti piu' rilevanti.

Il `.copy()` non cambia il risultato, ma elimina il `SettingWithCopyWarning`,
rendendo il test piu' pulito.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_relevant_sources(df, num_of_sources)
```

Il valore restituito non e' cambiato:

```python
return fig, table_relevant_sources
```

Quindi la Shiny dashboard dovrebbe continuare a chiamarla senza modifiche.

## `functions/get_bradfordlaw.py`

### Cosa non andava nella vecchia funzione

Anche questa funzione partiva da:

```python
data = df.get()
```

quindi era legata al contenitore reattivo della dashboard e non poteva essere
usata direttamente con il `pd.DataFrame` standardizzato prodotto dalla pipeline
ETL.

La funzione dipende dalla colonna `SO`, cioe' la fonte/rivista. Se la
standardizzazione non produce `SO` in modo corretto, Bradford's Law non puo'
calcolare la distribuzione delle fonti nelle tre zone.

Inoltre, la vecchia funzione accedeva al bordo della zona core con un indice che
poteva essere fragile su dataset piccoli o con poche fonti.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `numpy`;
  - `pandas`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta validazione minima della colonna `SO`.
- Filtrate le fonti vuote.
- Reso piu' robusto l'accesso al limite della zona core nel grafico.

### Perche'

La patch consente alla funzione di accettare:

```python
get_bradford_law(df_pandas)
get_bradford_law(df_shiny_reactive)
```

e verifica che la standardizzazione delle fonti sia sufficiente per calcolare
Bradford's Law.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_bradford_law(df)
```

Il valore restituito non e' cambiato:

```python
return fig, df_bradford
```

Questa funzione e' facile da provare in Biblioshiny perche' corrisponde alla
sezione:

```text
Sources -> Bradford's Law
```

La sezione viene calcolata direttamente quando si apre il pannello, come
`Annual Scientific Production`.

## `functions/get_relevantauthors.py`

### Cosa non andava nella vecchia funzione

Anche questa funzione partiva dalla stessa assunzione fragile:

```python
data = df.get()
```

Quindi era legata al contenitore reattivo della dashboard e non poteva essere
usata comodamente passando direttamente il `pd.DataFrame` prodotto dalla pipeline
ETL.

Questa funzione e' utile per testare la standardizzazione perche' usa `AU`, una
colonna multi-valore che secondo la traccia deve essere una `list[str]`. Se la
pipeline producesse autori come stringhe separate da `;` invece che liste, la
funzione potrebbe svuotare gli autori o produrre risultati sbagliati.

Un altro dettaglio riguarda il parametro `frequency`. Dalla dashboard arrivano
valori come:

```text
n_docs
percentage
freq_measure
```

La vecchia funzione gestiva solo alcuni casi e poteva usare come intestazione di
colonna il valore tecnico `n_docs`, meno leggibile del nome finale.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `pandas`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta la normalizzazione del parametro `frequency`.
- Aggiunta validazione minima della colonna `AU`.
- Filtrate le righe senza lista autori valida.
- Corretta la logica della frequenza frazionata per non dipendere dall'indice
  del DataFrame.

### Perche'

La patch consente alla funzione di accettare:

```python
get_relevant_authors(df_pandas, 10, frequency="n_docs")
get_relevant_authors(df_shiny_reactive, 10, frequency="n_docs")
```

e allo stesso tempo verifica che il DataFrame standardizzato contenga davvero
`AU` come lista di autori.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_relevant_authors(df, num_of_authors, frequency)
```

Il valore restituito non e' cambiato:

```python
return fig, table_relevant_authors
```

La dashboard puo' continuare a passarle i valori tecnici dell'input select
(`n_docs`, `percentage`, `freq_measure`), che ora vengono convertiti in etichette
leggibili.

## `functions/get_lotkalaw.py`

### Cosa non andava nella vecchia funzione

La funzione partiva dalla stessa assunzione fragile:

```python
data = df.get()
```

Quindi funzionava nel contesto Shiny, ma non era comoda da usare direttamente
con il `pd.DataFrame` standardizzato dalla pipeline ETL.

In piu', questa funzione dipende fortemente da `AU`, che deve essere una lista
di autori. Se `AU` non fosse una lista, il calcolo della produttivita' autoriale
potrebbe diventare errato.

Infine, la stima della curva teorica con `np.polyfit` richiede almeno due livelli
di produttivita'. Su dataset piccoli o molto uniformi, la vecchia funzione poteva
non avere abbastanza punti per stimare la curva.

### Cosa e' stato modificato

- Sostituito `from www.services import *` con import espliciti:
  - `numpy`;
  - `pandas`;
  - `plotly.graph_objects`.
- Aggiunta la funzione helper `_resolve_dataframe(df)`.
- Aggiunta validazione minima della colonna `AU`.
- Filtrate le righe senza lista autori valida.
- Aggiunta protezione quando esiste un solo livello di produttivita' autoriale.

### Perche'

La patch consente alla funzione di accettare:

```python
get_lotka_law(df_pandas)
get_lotka_law(df_shiny_reactive)
```

e verifica che la standardizzazione degli autori sia adatta a una legge
bibliometrica basata sulla produttivita' degli autori.

### Impatto sulla dashboard

La firma della funzione non e' cambiata:

```python
get_lotka_law(df)
```

Il valore restituito non e' cambiato:

```python
return fig, author_prod
```

Quindi la sezione Biblioshiny:

```text
Authors -> Lotka's Law
```

dovrebbe continuare a funzionare senza modifiche lato `app.py`.

## `tests/test_annual_production_smoke.py`

### Cosa e' stato creato

E' stato creato un file di test `unittest` che verifica sette funzioni:

- `get_annual_production`;
- `get_average_citations`;
- `get_cited_documents`;
- `get_bradford_law`;
- `get_relevant_sources`.
- `get_relevant_authors`.
- `get_lotka_law`.

Ogni funzione viene testata in due modi:

1. passando un `pd.DataFrame` diretto;
2. passando un piccolo wrapper `DataFrameBox` con metodo `.get()`, che simula
   il comportamento del `reactive.Value` usato da Shiny.

Prima di chiamare le funzioni, il test esegue la catena ETL completa su un file
grezzo:

```text
sources/Scopus/Scopus.csv
```

Il percorso testato e':

```text
Scopus.csv -> extract_from_file -> convert2df(validate=True) -> funzione analitica
```

In questo modo il test non verifica solo che la funzione non vada in errore, ma
anche che la standardizzazione produca un DataFrame nel formato richiesto.

### Perche'

Questo test serve a dimostrare tre cose:

- la pipeline ETL produce un DataFrame conforme al contratto Bibliometrix;
- uso interno alla Shiny dashboard;
- uso esterno in script Python o notebook.

Il test controlla esplicitamente che il DataFrame standardizzato abbia tutte le
colonne previste e che ogni colonna rispetti il tipo atteso (`str`, `int` o
`list`).

### Perche' usa `importlib`

Il test carica direttamente i singoli file delle funzioni invece di importare
tutto il package `functions`.

Questo evita che il test di una singola funzione importi inutilmente tutte le
altre funzioni e dipendenze del progetto.

## `scripts/run_annual_production_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_annual_production`;
5. salva risultati reali in `analysis_results/annual_production/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `annual_production_table.csv`;
- `annual_production_plot.html`;
- `annual_production_summary.txt`.

### Perche'

Il test automatico dice solo che la funzione non va in errore.
Questo script serve invece a ottenere risultati da analizzare:

- DataFrame standardizzato esportato;
- report del contratto ETL;
- tabella annuale;
- grafico interattivo;
- sintesi testuale.

## `scripts/run_relevant_sources_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_relevant_sources`;
5. salva risultati reali in `analysis_results/relevant_sources/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `relevant_sources_table.csv`;
- `relevant_sources_top_10.csv`;
- `relevant_sources_plot.html`;
- `relevant_sources_summary.txt`.

### Perche'

Serve a trasformare la funzione patchata in uno strumento pratico per analisi:

- lista completa delle fonti;
- top fonti piu' frequenti;
- grafico interattivo;
- sintesi con numero di fonti e concentrazione delle top fonti.

## `scripts/run_bradford_law_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_bradford_law`;
5. salva risultati reali in `analysis_results/bradford_law/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `bradford_law_table.csv`;
- `bradford_law_plot.html`;
- `bradford_law_summary.txt`.

### Perche'

Serve a verificare una funzione facilmente controllabile anche da dashboard, ma
comunque utile per la traccia perche' dipende da `SO`, cioe' dalla corretta
standardizzazione delle fonti.

## `scripts/run_average_citations_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_average_citations`;
5. salva risultati reali in `analysis_results/average_citations/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `average_citations_table.csv`;
- `average_citations_plot.html`;
- `average_citations_summary.txt`.

### Perche'

Serve a verificare una funzione che dipende da `PY` e `TC`, quindi controlla un
altro aspetto della standardizzazione: non solo colonne e liste, ma anche valori
numericamente utilizzabili per calcoli su citazioni e anni.

## `scripts/run_cited_documents_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_cited_documents`;
5. salva risultati reali in `analysis_results/cited_documents/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `cited_documents_table.csv`;
- `cited_documents_top_10.csv`;
- `cited_documents_plot.html`;
- `cited_documents_summary.txt`.

### Perche'

Serve a verificare una funzione molto confrontabile con Biblioshiny e utile per
la traccia perche' dipende contemporaneamente da:

- `SR`, cioe' il riferimento breve del documento;
- `DI`, cioe' il DOI;
- `TC`, cioe' le citazioni totali;
- `PY`, cioe' l'anno di pubblicazione.

Se la standardizzazione non produce queste colonne nel formato atteso, questa
analisi non puo' funzionare correttamente.

## `scripts/run_relevant_authors_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_relevant_authors`;
5. salva risultati reali in `analysis_results/relevant_authors/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `relevant_authors_table.csv`;
- `relevant_authors_top_10.csv`;
- `relevant_authors_plot.html`;
- `relevant_authors_summary.txt`.

### Perche'

Serve a verificare una funzione che dipende da una colonna multi-valore (`AU`).
Questo e' importante per la traccia, perche' non basta che le colonne esistano:
alcune colonne devono anche avere il tipo giusto, cioe' liste Python.

## `scripts/run_lotka_law_analysis.py`

### Cosa e' stato creato

Uno script operativo che:

1. legge un file bibliografico grezzo;
2. esegue `extract_from_file`;
3. esegue `convert2df(validate=True)`;
4. chiama `get_lotka_law`;
5. salva risultati reali in `analysis_results/lotka_law/`.

Output prodotti:

- `standardized_dataframe.csv`;
- `standardization_report.txt`;
- `lotka_law_table.csv`;
- `lotka_law_plot.html`;
- `lotka_law_summary.txt`.

### Perche'

Serve a verificare una funzione bibliometrica basata sulla produttivita'
autoriale. Anche qui la standardizzazione di `AU` e' centrale, ma il risultato e'
diverso da `get_relevant_authors`: invece della classifica degli autori, produce
la distribuzione osservata e teorica della produttivita' autoriale.

## Salvataggio dei plot HTML

### Cosa non andava nella versione precedente

Gli script salvavano i grafici con:

```python
fig.write_html(html_path, include_plotlyjs=True, full_html=True)
```

Questa opzione incorpora tutta la libreria JavaScript di Plotly dentro ogni file
HTML. In alcuni casi Plotly veniva scritto in una singola riga molto lunga: il
file funzionava nel browser, ma aprirlo in VS Code poteva causare lag.

### Cosa e' stato modificato

E' stata aggiunta la funzione comune:

```python
write_plot_html(fig, output_file)
```

in `scripts/etl_analysis_common.py`.

Ora tutti gli script usano:

```python
fig.write_html(output_file, include_plotlyjs="directory", full_html=True)
```

### Perche'

Con `include_plotlyjs="directory"` il file HTML contiene solo il grafico e un
riferimento a `plotly.min.js`, salvato nella stessa cartella. In questo modo:

- gli HTML passano da circa 4.4 MB a circa 9-19 KB;
- non ci sono piu' righe JavaScript enormi dentro gli HTML;
- i plot restano apribili offline, a patto di lasciare `plotly.min.js` accanto
  al rispettivo file HTML.

## `analysis_results/`

### Cosa e' stato generato

Sono stati generati file di output reali per le funzioni testate.

Per `get_annual_production`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- documenti con anno valido: `1000`;
- intervallo anni: `2024-2025`;
- anno con picco: `2024`, con `999` documenti.

Per `get_average_citations`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- documenti con anno valido: `1000`;
- intervallo anni: `2024-2025`;
- anno con maggiore media citazioni/anno: `2024`, con `0.01`;
- anno con maggiore media citazioni/articolo: `2024`, con `0.02`.

Per `get_cited_documents`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- documenti unici nella tabella: `997`;
- documenti con almeno una citazione: `22`;
- citazioni totali: `22`;
- metrica usata: `Total Citations`;
- citazioni del documento in prima posizione: `1`;
- citazioni totali dei top 10 documenti: `10`.

Per `get_relevant_sources`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- documenti con fonte valida: `1000`;
- fonti uniche: `183`;
- fonte principale: `BMC HEALTH SERVICES RESEARCH`;
- documenti della fonte principale: `129`;
- quota delle top 10 fonti: `46.6%`.

Per `get_bradford_law`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- documenti con fonte valida: `1000`;
- fonti uniche: `183`;
- fonti core: `4`;
- documenti nelle fonti core: `332`;
- quota documenti nelle fonti core: `33.2%`;
- Zone 1: `4` fonti, `332` documenti;
- Zone 2: `26` fonti, `340` documenti;
- Zone 3: `153` fonti, `328` documenti.

Per `get_relevant_authors`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- autori unici: `6427`;
- metrica usata: `N. of Documents`;
- autore principale: `Wang X.`;
- documenti dell'autore principale: `13`;
- totale documenti associati ai top 10 autori: `89`.

Per `get_lotka_law`:

- file grezzo: `sources/Scopus/Scopus.csv`;
- record grezzi estratti: `1000`;
- righe standardizzate: `1000`;
- colonne mancanti nel contratto ETL: `none`;
- errori di tipo nel contratto ETL: `none`;
- autori unici: `6427`;
- massimo articoli per un autore: `13`;
- autori con un solo articolo: `6113`;
- quota autori con un solo articolo: `95.11%`;
- somma frequenze osservate: `1.0`;
- somma frequenze teoriche: `1.0`.

### Perche'

Questi file dimostrano che le funzioni non solo superano i test, ma producono
anche risultati concreti e ispezionabili.

## Note sulla dashboard Biblioshiny

### Dove trovare `get_relevant_sources`

Nella dashboard non esiste una voce chiamata `relevant_sources_plot`. Quello e'
il nome del file HTML generato dallo script esterno, non il nome della sezione
visibile in Biblioshiny.

La funzione `get_relevant_sources` corrisponde alla sezione:

```text
Sources -> Most Relevant Sources
```

Nel codice `app.py`, la sezione ha valore interno:

```text
most_relevant_sources
```

Dentro quella pagina ci sono due tab:

- `Plot`;
- `Table`.

A differenza di `Annual Scientific Production`, questa analisi non parte
automaticamente. Bisogna cliccare:

```text
Run Analysis
```

solo dopo viene popolato il grafico.

### Dove trovare `get_cited_documents`

La funzione `get_cited_documents` corrisponde alla sezione:

```text
Documents -> Most Global Cited Documents
```

Nel codice `app.py`, la sezione ha valore interno:

```text
most_global_cited_documents
```

Dentro quella pagina ci sono due tab:

- `Plot`;
- `Table`.

Anche questa analisi non parte automaticamente. Bisogna cliccare:

```text
Run Analysis
```

La dashboard passa alla funzione gli stessi valori gestiti dallo script:

```text
total_cit
total_cit_per_year
```

### Perche' il risultato di Annual Production puo' essere diverso

Lo script esterno:

```powershell
python scripts\run_annual_production_analysis.py
```

usa di default:

```text
sources/Scopus/Scopus.csv
```

Lo script parte quindi dal file grezzo Scopus, lo standardizza e poi chiama la
funzione. La dashboard, invece, usa il DataFrame attualmente caricato nella
sessione Shiny. Se nella dashboard e nello script non si sta usando esattamente
lo stesso file grezzo e la stessa pipeline, i risultati saranno diversi.

Esempio: lo script ha prodotto questi risultati sul file grezzo
`sources/Scopus/Scopus.csv`:

```text
Raw records: 1000
Standardized rows: 1000
Documents with valid year: 1000
Year range: 2024-2025
Peak year: 2024 (999 documents)
```

Per confrontare correttamente dashboard e script, bisogna usare lo stesso
dataset in entrambi i casi. Se carichi in dashboard il sample dataset interno,
non devi confrontarlo con lo script lanciato su `sources/Scopus/Scopus.csv`.

Un'altra causa possibile e' che la dashboard fosse gia' avviata prima della
patch. In quel caso Shiny puo' continuare a usare il codice caricato in memoria.
Dopo modifiche a file Python come `functions/get_annualproduction.py` o
`functions/get_relevantsources.py`, conviene riavviare la dashboard.

## Comandi principali

Eseguire tutti i test:

```powershell
python -m unittest tests.test_annual_production_smoke
```

Generare risultati per la produzione annuale:

```powershell
python scripts\run_annual_production_analysis.py
```

Generare risultati per le citazioni medie per anno:

```powershell
python scripts\run_average_citations_analysis.py
```

Generare risultati per i documenti piu' citati globalmente:

```powershell
python scripts\run_cited_documents_analysis.py --num-documents 10 --measure total_cit
```

Generare risultati per le fonti piu' rilevanti:

```powershell
python scripts\run_relevant_sources_analysis.py --num-sources 10
```

Generare risultati per Bradford's Law:

```powershell
python scripts\run_bradford_law_analysis.py
```

Generare risultati per gli autori piu' rilevanti:

```powershell
python scripts\run_relevant_authors_analysis.py --num-authors 10 --frequency n_docs
```

Generare risultati per la legge di Lotka:

```powershell
python scripts\run_lotka_law_analysis.py
```

Usare un file grezzo diverso:

```powershell
python scripts\run_annual_production_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_average_citations_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_cited_documents_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_bradford_law_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_relevant_sources_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_relevant_authors_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
python scripts\run_lotka_law_analysis.py --input "percorso\file_grezzo.csv" --source SCOPUS
```

## Nota sull'ambiente virtuale

Durante lo sviluppo e' stata usata una cache temporanea di `uv` solo per
installare le dipendenze necessarie ai test (`pandas`, `openpyxl`, `plotly`,
`ipywidgets`). Non e' stato lasciato alcun ambiente virtuale dentro il progetto.
