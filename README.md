# PullRadar cloud — mercato e notizie GCC Pokémon

Automazione Instagram in italiano ospitata su GitHub Actions. Segue sei carte dei set **30° Anniversario**, **Caos Nascente** e **Buio Pesto**. [TCGdex](https://tcgdex.dev/rest/card) dà nome, set e numero. [CardTrader](https://www.cardtrader.com/it/docs/api/full/reference) fornisce offerte filtrate per lingua italiana e stampa. Il valore mostrato è la media delle cinque offerte italiane Near Mint meno care, senza spedizione: è un prezzo richiesto, non una vendita conclusa.

Le carte mostrate nelle grafiche sono le immagini italiane fornite dall'utente, associate alla stampa esatta tramite il numero della carta. Le illustrazioni generate sono usate soltanto come sfondi. La stampa `30th-c-001` non è monitorata: l'immagine di Charizard ricevuta ritrae invece il Set Base 4/102.

## Programmazione

GitHub Actions prepara e programma alle 07:17 e riprova alle 07:37 (Europe/Rome), senza Mac o chat. Buffer riceve tre caroselli alle **09:00, 13:00 e 19:00** e due storie alle **11:00 e 20:00**. La storia delle 20 viene programmata soltanto se Buffer conferma che il carosello delle 19 è stato inviato; il flusso prova alle 19:05, 19:15, 19:25 e 19:35. Alle 21:15 un controllo verifica i cinque stati e segnala un errore se manca un invio. GitHub può ritardare i flussi programmati; uno slot troppo vicino viene saltato.

Il carosello delle 09:00 segue sempre una chase card. Gli altri due scelgono tra ricerche globali, annuncio ufficiale, notizia giapponese, indiscrezione e carte seguite. Quando non c'è una notizia recente e citabile, il sistema presenta una carta senza attribuirle un prezzo non verificato; non inventa leak o lanci. Un articolo già programmato viene ricordato in `state.json` e non viene ripetuto. Il piano del giorno è salvato in `plan.json` per evitare che il tentativo serale generi contenuti diversi.

## Fonti e controlli editoriali

- **Mercato italiano:** sette carte di `cards.json`. CardTrader filtra `language=it`; il programma ricontrolla `pokemon_language=it`, `condition=Near Mint`, identificativo della stampa e valuta EUR. Richiede almeno cinque offerte valide. `snapshots.json` conserva il dato quotidiano e confronta solo la stessa metrica. La prima rilevazione mostra “precedente: prima rilevazione”; dal secondo giorno il nuovo prezzo diventa verde se sale e rosso se scende. I vecchi dati europei aggregati non sono usati nel confronto. Se mancano il token o almeno tre carte con prezzi verificati, la programmazione si ferma invece di pubblicare prezzi generici.
- **Più cercate:** [Google Trends](https://trends.google.com/trends/explore) confronta fino a cinque query del tipo `nome pokemon card` su scala mondiale negli ultimi sette giorni. L'indice è relativo a quelle query: non è una classifica di tutte le carte né un numero assoluto di ricerche. Se Trends non risponde, il format viene omesso.
- **Annunci ufficiali:** lettura della [pagina prodotti giapponese](https://www.pokemon-card.com/info/) con data, titolo e link; l'anteprima ufficiale di [Dominio Delta](https://www.pokemon.com/us/features/sneak-a-peek-at-cards-from-the-mega-evolution-delta-reign-expansion) del 5 ottobre è inclusa come evento datato e scade automaticamente.
- **Giappone e indiscrezioni:** titoli recenti di [PokéBeach](https://www.pokebeach.com/) con link diretto. Le indiscrezioni sono marcate **non confermate**; nessun dettaglio oltre il titolo viene presentato come fatto. Tutte le notizie hanno una finestra massima di quattro giorni e sono citate nelle didascalie.

Il passaggio `Read Instagram insights` prova a leggere metriche dei post inviati. Dopo almeno tre post con visualizzazioni per una carta, può darle priorità nella rotazione. Gli insight grezzi e la chiave restano fuori dal repository. Se l'API non restituisce metriche, le pubblicazioni continuano.

## Configurazione

- Secret Actions `BUFFER_API_KEY`: chiave Buffer personale.
- Secret Actions `CARDTRADER_API_TOKEN`: token CardTrader dell'account, usato solo per leggere catalogo e offerte.
- Variable Actions `BUFFER_CHANNEL_ID`: ID del canale Instagram collegato.
- Repository pubblico, così Buffer può scaricare le immagini create dal flusso.

Il workflow verifica il canale Buffer prima di creare media. I post già registrati in `state.json` non vengono creati due volte. **Actions → PullRadar quotidiano → Run workflow** permette una prova manuale. Uno stato `sent` di Buffer conferma l'invio secondo Buffer; la presenza effettiva su Instagram va verificata nel primo ciclo reale.
