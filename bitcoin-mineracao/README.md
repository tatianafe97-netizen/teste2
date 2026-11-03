# Mineração de Bitcoin em 50s: vídeo vertical narrado em Canvas

Animação viral minimalista (bonequinhos palito + vetores 2D) explicando como funciona a mineração de Bitcoin.
Formato Shorts/TikTok/Reels: **9:16 · 1080×1920 · 60fps · 49,5 segundos**, com narração em voz neural.

Tudo está em um único arquivo, `index.html`, que usa HTML5 Canvas e JavaScript puro. Os desenhos são feitos por código, os efeitos sonoros são sintetizados com Web Audio API e a narração vem embutida no próprio HTML (MP3 em base64, cerca de 0,5 MB). Não há imagens nem arquivos de áudio externos.

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
| Narração com voz neural | Locução embutida (voz pt-BR do Kokoro). Com ela ligada, a trilha e os efeitos abaixam para a voz ficar na frente |
| Batida de fundo | Kick, hi-hat e baixo sintéticos a 120 BPM |
| Repetir em loop | Emenda o fim no começo: a última cena dá zoom de volta ao minerador da cena 1 |
| `Espaço` / `R` / `F` | Pausar, reiniciar e tela cheia |
| `?t=33.5` na URL | Congela um quadro específico (útil para thumbnail) |
| `?debug` na URL | Mostra o tempo e a cena atuais |

A fonte Montserrat vem do Google Fonts. Sem internet, o navegador usa Arial Black como alternativa e tudo continua funcionando.

## Como gerar o arquivo de vídeo

**Opção 1: direto no navegador.** O botão **● Gravar vídeo em arquivo** toca o vídeo inteiro e baixa um `.mp4` (Chrome/Edge recentes) ou `.webm`, com narração, efeitos e batida. Mantenha a aba visível durante a gravação. Essa gravação acontece em tempo real, então o resultado só sai em 60fps cravados se o computador conseguir desenhar em 60fps.

Para converter `.webm` em `.mp4`:

```bash
ffmpeg -i mineracao-bitcoin-9x16.webm -c:v libx264 -pix_fmt yuv420p -r 60 -crf 18 -c:a aac -b:a 192k mineracao.mp4
```

**Opção 2: exportação offline quadro a quadro (recomendada para publicar).** Renderiza cada quadro em t = n/60 e a trilha sonora (narração + efeitos + batida) com `OfflineAudioContext`. O resultado é um MP4 H.264 + AAC sem nenhum quadro perdido, em qualquer máquina, e um `.srt` com as legendas.

```bash
cd bitcoin-mineracao
npm i playwright && npx playwright install chromium   # uma vez
node exportar-video.js                                # → mineracao-bitcoin-9x16-60fps.mp4 + .srt
node exportar-video.js saida.mp4 --sem-batida --crf=16
node exportar-video.js saida.mp4 --sem-voz            # só efeitos e batida (para locução própria)
```

Requer Node 18+ e `ffmpeg` no PATH. Em uma máquina comum leva de 2 a 6 minutos.

## Narração

A voz é gerada pelo [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (licença Apache-2.0), um modelo neural que roda no próprio computador, sem serviço pago nem chave de API. O script `gerar-narracao.py`:

1. lê o texto de cada cena do array `SCENES` do `index.html`;
2. sintetiza cada cena e calibra a velocidade para o total caber na duração alvo (padrão 49,5s);
3. mede o instante exato de cada palavra com o Whisper (`faster-whisper`), para as legendas acenderem junto com a fala;
4. grava o áudio e os tempos dentro do `index.html`, entre os marcadores `NARRACAO_INICIO` e `NARRACAO_FIM`.

A duração de cada cena e todas as animações (corte para o galpão, cadeado, caça-níquel, correntes, chuva de moedas) se ajustam a esses tempos. Para trocar a voz ou regenerar depois de editar o roteiro:

```bash
pip install kokoro-onnx soundfile numpy faster-whisper
# baixe kokoro-v1.0.onnx e voices-v1.0.bin de
# https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 para bitcoin-mineracao/modelos/
python3 gerar-narracao.py                     # voz masculina pm_alex (padrão)
python3 gerar-narracao.py --voz pf_dora       # voz feminina
python3 gerar-narracao.py --voz pm_santa --duracao 48
```

## Roteiro e sincronização

O tempo de tudo sai de um único relógio (`AudioContext.currentTime`): a narração, os efeitos sonoros (agendados com 120 ms de antecedência) e o quadro desenhado a cada `requestAnimationFrame`. As legendas destacam em amarelo a palavra que está sendo falada, e as animações principais são disparadas pela palavra narrada. Por exemplo, o cronômetro surge em "dez minutos" e as correntes caem em "acorrentado".

| Tempo | Cena | O que acontece |
|---|---|---|
| 00,0–07,6s | O Gancho | Minerador de capacete martela o PC, que explode num X vermelho piscando; corte para o galpão de máquinas com bilhete, neon "LOTERIA" e etiqueta "$$$" |
| 07,6–15,9s | O Livro-Razão | Bonequinhos ao redor do globo lançam transações brilhantes para dentro do bloco de vidro até 100% |
| 15,9–25,3s | A Loteria do Hash | Cadeado SHA-256 tranca o bloco (e eletrocuta um fraudador); caça-níquel de nonce gira trilhões de tentativas |
| 25,3–34,3s | Guerra de Energia | Dois bonequinhos suando diante de pilhas de ASICs em chamas; medidor no vermelho, cidade apagando, cronômetro de 10 min |
| 34,3–41,8s | Prova de Trabalho | "HASH ENCONTRADO!", a rede confere, bloco lacrado (tremor forte) e acorrentado à Blockchain |
| 41,8–49,5s | A Recompensa | O bloco abre e cospe moedas ₿ na cabeça do vencedor (+3,125 BTC); zoom rápido de volta à cena 1 (loop) |

Os tempos acima saem da narração atual. Sem narração embutida, o vídeo usa a divisão original de 48s (4 / 8 / 10 / 10 / 10 / 6 s).
