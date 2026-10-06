# PullRadar cloud gratuito — pilota mercato

Questo progetto prepara caroselli e storie statiche da dati TCGdex, poi li programma su Buffer. È un **pilota**: non pubblica news, leak o classifiche di ricerca. Non usa scansioni delle carte. Le due illustrazioni sono fan art originali già preparate per PullRadar; il layout dichiara che non sono immagini della carta.

## Servizi gratuiti

- Repository **pubblico** GitHub: Actions standard e file pubblici.
- Buffer Free: fino a 10 elementi contemporanei in coda, API inclusa.
- TCGdex: schede italiane e prezzi Cardmarket UE quando presenti.

## Attivazione

1. Crea un repository GitHub pubblico chiamato `pullradar-cloud` e carica il contenuto di questa cartella nella radice.
2. In Buffer, apri **Settings → API** e genera una chiave personale. Non inserirla nei file o nella chat.
3. Nel repository GitHub, vai su **Settings → Secrets and variables → Actions**. Crea il secret `BUFFER_API_KEY` con la chiave e la variable `BUFFER_CHANNEL_ID` con l'ID del canale Instagram.
4. Avvia **Actions → PullRadar quotidiano → Run workflow**. Controlla il log e la coda Buffer prima di lasciare la programmazione quotidiana attiva.
5. Dopo una pubblicazione riuscita, disattiva l'automazione locale per evitare doppioni.

Lo script non pubblica se la fonte prezzi è più vecchia di 48 ore, se la valuta non è EUR, se mancano dati delle due carte, o se i contenuti del giorno sono già stati programmati. I prezzi sono **trend Cardmarket UE indicativi** e non promesse di vendita o prezzi specifici per lingua/condizione. La storia di rimando dice di aprire il post nel profilo: Buffer non aggiunge automaticamente link o sticker alla storia.

Il repository è pubblico: immagini e stato della pubblicazione sono visibili a tutti. La chiave Buffer deve stare esclusivamente nei Secrets di GitHub.

La programmazione GitHub può subire ritardi. Il sistema prepara i contenuti al mattino e Buffer gestisce gli orari 09:00, 11:00, 13:00, 19:00 e 20:00 Europe/Rome, se sono ancora futuri. Non promette cinque uscite ogni giorno quando i dati non superano i controlli.
