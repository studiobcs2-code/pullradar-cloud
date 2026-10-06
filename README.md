# PullRadar cloud — mercato Pokémon 30° anniversario

Automazione Instagram gratuita per due Pikachu-ex del set italiano **30° Anniversario** (`30th-149` e `30th-150`). La [guida prezzi ufficiale Cardmarket](https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json) fornisce il trend in euro e l'ora di aggiornamento; TCGdex fornisce nome, set e numero. Le immagini sono illustrazioni originali del soggetto, non scansioni delle carte. Il numero della carta e il link alla scheda dati sono sempre nella didascalia.

## Programmazione

GitHub Actions esegue il flusso alle 07:17 e alle 19:25 (Europe/Rome), senza dipendere dal Mac o da questa chat. Buffer programma tre caroselli alle 09:00, 13:00 e 19:00, una storia alle 11:00 e una storia di rimando alle 20:00. La storia delle 20 viene programmata solo quando Buffer conferma che il post delle 19 è stato inviato. Alle 21:15 un terzo flusso controlla che Buffer riporti tutti e cinque i contenuti come inviati: un'assenza o un errore rende rossa l'esecuzione GitHub Actions. I ritardi del servizio possono far saltare uno slot.

Lo script ferma la giornata se un prezzo manca, non è in EUR o ha più di 48 ore. `snapshots.json` conserva fino a 60 rilevazioni giornaliere per carta. La variazione compare solo dopo una rilevazione precedente della **stessa metrica**; non viene ricavata da prezzi di vendita o offerte isolate. I trend UE non rappresentano il prezzo di una specifica copia italiana.

Il passaggio `Read Instagram insights` prova a leggere le metriche dei post inviati. Se sono disponibili almeno tre post con visualizzazioni per ciascuna variante, mette per prima quella con il migliore rapporto tra salvataggi, condivisioni, commenti e visualizzazioni. I valori grezzi e la chiave non vengono salvati nel repository. Se l'API non dà metriche, l'ordine resta neutro e le pubblicazioni possono continuare.

## Configurazione

- Secret Actions `BUFFER_API_KEY`: chiave Buffer personale.
- Variable Actions `BUFFER_CHANNEL_ID`: ID del canale Instagram collegato.
- Repository pubblico, così Buffer può scaricare le immagini create dal flusso.

Il workflow verifica il canale Buffer prima di generare e programmare. I post già registrati in `state.json` non vengono creati due volte. Una prova con **Actions → PullRadar quotidiano → Run workflow** verifica credenziali, dati e generazione; un'esecuzione dopo l'ultimo slot non programma nuove uscite.

## Ambito attuale

Questo progetto pubblica contenuti di **mercato**. News dei set giapponesi, annunci ufficiali, leak e classifiche delle carte più cercate richiedono fonti e regole editoriali dedicate; non sono attivi qui. Nessun numero o evento di questi format viene inventato per riempire il calendario.
