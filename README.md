# PullRadar cloud — mercato e notizie GCC Pokémon

Automazione Instagram in italiano ospitata su GitHub Actions. Segue sette carte dei set **30° Anniversario**, **Collezione Classica del 30°**, **Caos Nascente** e **Buio Pesto**. La [guida prezzi Cardmarket](https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json) dà il trend in euro e l'ora dell'aggiornamento; [TCGdex](https://tcgdex.dev/rest/card) dà nome, set e numero. Il trend UE non è il prezzo di una carta italiana specifica.

Le grafiche pubblicate mostrano illustrazioni originali o dettagli elaborati delle carte, senza riprodurre una carta completa. Il carosello su **Mega Golisopod-ex** del 7 ottobre 2026 usa un dettaglio ricavato dalle immagini italiane fornite dall'utente. Le scansioni integrali non sono caricate nel repository né pubblicate.

## Programmazione

GitHub Actions prepara e programma alle 07:17 e riprova alle 07:37 (Europe/Rome), senza Mac o chat. Buffer riceve tre caroselli alle **09:00, 13:00 e 19:00** e due storie alle **11:00 e 20:00**. La storia delle 20 viene programmata soltanto se Buffer conferma che il carosello delle 19 è stato inviato; il flusso prova alle 19:05, 19:15, 19:25 e 19:35. Alle 21:15 un controllo verifica i cinque stati e segnala un errore se manca un invio. GitHub può ritardare i flussi programmati; uno slot troppo vicino viene saltato.

Il carosello delle 09:00 è sempre sul mercato. Gli altri due scelgono tra ricerche globali, annuncio ufficiale, notizia giapponese, indiscrezione e mercato. Quando non c'è una notizia recente e citabile, il sistema usa un aggiornamento di mercato; non inventa leak o lanci. Un articolo già programmato viene ricordato in `state.json` e non viene ripetuto. Il piano del giorno è salvato in `plan.json` per evitare che il tentativo serale generi contenuti diversi.

## Fonti e controlli editoriali

- **Mercato:** sette carte di `cards.json`, trend Cardmarket in EUR aggiornato entro 48 ore. Se una carta manca viene esclusa; se restano meno di tre carte, il flusso si ferma. `snapshots.json` conserva fino a 60 giorni per carta e confronta soltanto la stessa metrica.
- **Più cercate:** [Google Trends](https://trends.google.com/trends/explore) confronta fino a cinque query del tipo `nome pokemon card` su scala mondiale negli ultimi sette giorni. L'indice è relativo a quelle query: non è una classifica di tutte le carte né un numero assoluto di ricerche. Se Trends non risponde, il format viene omesso.
- **Annunci ufficiali:** lettura della [pagina prodotti giapponese](https://www.pokemon-card.com/info/) con data, titolo e link; l'anteprima ufficiale di [Dominio Delta](https://www.pokemon.com/us/features/sneak-a-peek-at-cards-from-the-mega-evolution-delta-reign-expansion) del 5 ottobre è inclusa come evento datato e scade automaticamente.
- **Giappone e indiscrezioni:** titoli recenti di [PokéBeach](https://www.pokebeach.com/) con link diretto. Le indiscrezioni sono marcate **non confermate**; nessun dettaglio oltre il titolo viene presentato come fatto. Tutte le notizie hanno una finestra massima di quattro giorni e sono citate nelle didascalie.

Il passaggio `Read Instagram insights` prova a leggere metriche dei post inviati. Dopo almeno tre post con visualizzazioni per una carta, può darle priorità nella rotazione. Gli insight grezzi e la chiave restano fuori dal repository. Se l'API non restituisce metriche, le pubblicazioni continuano.

## Configurazione

- Secret Actions `BUFFER_API_KEY`: chiave Buffer personale.
- Variable Actions `BUFFER_CHANNEL_ID`: ID del canale Instagram collegato.
- Repository pubblico, così Buffer può scaricare le immagini create dal flusso.

Il workflow verifica il canale Buffer prima di creare media. I post già registrati in `state.json` non vengono creati due volte. **Actions → PullRadar quotidiano → Run workflow** permette una prova manuale. Uno stato `sent` di Buffer conferma l'invio secondo Buffer; la presenza effettiva su Instagram va verificata nel primo ciclo reale.
