# Mineração de Bitcoin em 48s: vídeo vertical em Canvas

Animação viral minimalista (bonequinhos palito + vetores 2D) explicando como funciona a mineração de Bitcoin.
Formato Shorts/TikTok/Reels: **9:16 · 1080×1920 · 60fps · 48 segundos**.

Tudo está em um único arquivo, `index.html`, que usa HTML5 Canvas e JavaScript puro. Os desenhos são feitos por código e os sons são sintetizados com Web Audio API, sem imagens nem arquivos de áudio externos.

## Como abrir

Dê um duplo clique em `index.html`, ou pelo terminal:

```bash
# Linux
xdg-open bitcoin-mineracao/index.html
# macOS
open bitcoin-mineracao/index.html
# Windows
start bitcoin-mineracao\index.html
```

Se preferir servir via HTTP: `python3 -m http.server 8000 -d bitcoin-mineracao` e acesse http://localhost:8000.

Clique em **▶ Iniciar Animação**. O clique é necessário porque os navegadores só liberam o áudio depois de uma interação do usuário.

| Opção / tecla | Função |
|---|---|
| Narração por voz sintética | Lê o roteiro com a Web Speech API (voz pt-BR do sistema), sincronizada no início de cada cena |
| Batida de fundo | Kick, hi-hat e baixo sintéticos a 120 BPM |
| Repetir em loop | Emenda o fim no começo: a última cena dá zoom de volta ao minerador da cena 1 |
| `Espaço` / `R` / `F` | Pausar, reiniciar e tela cheia |
| `?t=33.5` na URL | Congela um quadro específico (útil para thumbnail) |
| `?debug` na URL | Mostra o tempo e a cena atuais |

A fonte Montserrat vem do Google Fonts. Sem internet, o navegador usa Arial Black como alternativa e tudo continua funcionando.

## Como gerar o arquivo de vídeo

**Opção 1: direto no navegador.** O botão **● Gravar vídeo em arquivo** toca os 48s e baixa um `.mp4` (Chrome/Edge recentes) ou `.webm`, com vídeo e efeitos sonoros. Mantenha a aba visível durante a gravação. Essa gravação acontece em tempo real, então o resultado só sai em 60fps cravados se o computador conseguir desenhar em 60fps. A voz sintética não entra no arquivo, porque o navegador não permite capturá-la.

Para converter `.webm` em `.mp4`:

```bash
ffmpeg -i mineracao-bitcoin-9x16.webm -c:v libx264 -pix_fmt yuv420p -r 60 -crf 18 -c:a aac -b:a 192k mineracao.mp4
```

**Opção 2: exportação offline quadro a quadro (recomendada para publicar).** Renderiza exatamente 2.880 quadros (t = n/60) e a trilha sonora com `OfflineAudioContext`, e gera um MP4 H.264 + AAC sem perder nenhum quadro, em qualquer máquina. Também gera um `.srt` com as legendas, útil para gravar uma locução de verdade por cima.

```bash
cd bitcoin-mineracao
npm i playwright && npx playwright install chromium   # uma vez
node exportar-video.js                                # → mineracao-bitcoin-9x16-60fps.mp4 + .srt
node exportar-video.js saida.mp4 --sem-batida --crf=16
```

Requer Node 18+ e `ffmpeg` no PATH. Em uma máquina comum leva de 2 a 6 minutos.

## Roteiro e sincronização

O tempo de tudo sai de um único relógio (`AudioContext.currentTime`). A cada quadro, o `requestAnimationFrame` desenha a cena correspondente àquele instante, e os sons são agendados com 120 ms de antecedência no mesmo relógio. As legendas destacam cada palavra em amarelo. O tempo de cada palavra é distribuído pelo tamanho da palavra e pelas pausas de pontuação, e as animações principais são disparadas pela palavra narrada (ex.: o cronômetro surge em "dez minutos" e as correntes caem em "acorrentado").

| Tempo | Cena | O que acontece |
|---|---|---|
| 00–04s | O Gancho | Minerador de capacete martela o PC, que explode num X vermelho piscando; corte para galpão de máquinas com neon "LOTERIA" |
| 04–12s | O Livro-Razão | Bonequinhos ao redor do globo lançam transações brilhantes para dentro do bloco de vidro até 100% |
| 12–22s | A Loteria do Hash | Cadeado SHA-256 tranca o bloco (e eletrocuta um fraudador); caça-níquel de nonce gira trilhões de tentativas |
| 22–32s | Guerra de Energia | Dois bonequinhos suando diante de pilhas de ASICs em chamas; medidor no vermelho, cidade apagando, cronômetro de 10 min |
| 32–42s | Prova de Trabalho | "HASH ENCONTRADO!", a rede confere, bloco lacrado (tremor forte) e acorrentado à Blockchain |
| 42–48s | A Recompensa | O bloco abre e cospe moedas ₿ na cabeça do vencedor (+3,125 BTC); zoom rápido de volta à cena 1 (loop) |

O texto narrado de cada cena fica no array `SCENES`, no topo do script. Se você alterar o texto, as legendas e os gatilhos se reajustam sozinhos.
