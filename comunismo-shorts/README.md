# O Que É Comunismo? — vídeo vertical animado (Shorts/TikTok)

Animação minimalista com bonequinhos palito, em **HTML5 Canvas + JavaScript puro**, num único arquivo (`index.html`). Não usa nenhuma biblioteca nem arquivo externo.

- **Formato:** 9:16, canvas interno de 1080×1920, renderizado a cada `requestAnimationFrame` (60 fps em telas de 60 Hz)
- **Duração:** 48 s, em loop contínuo (o último quadro volta para a escova de dentes da Cena 1)
- **Legendas:** página curta no centro-inferior da tela, com a palavra atual destacada em amarelo
- **Áudio:** todos os efeitos são sintetizados com a Web Audio API: pop, swoosh, engrenagens, caixa registradora, alarme, impacto, raio-X, cadeado, evaporação, sino e uma batida de fundo
- **Narração:** uma voz neural pt-BR já vem gravada dentro do `index.html` (MP3 em base64, cerca de 375 KB). Ela toca pela Web Audio API, em sincronia com as animações, e entra na gravação do vídeo. No seletor "Narração" também dá para usar a voz do navegador (Web Speech API) ou desligar a voz.

## Como abrir

Basta abrir o arquivo no navegador (Chrome ou Edge recomendados):

```bash
# Linux
xdg-open comunismo-shorts/index.html
# macOS
open comunismo-shorts/index.html
# Windows
start comunismo-shorts\index.html
```

Se preferir servir por HTTP, rode `python3 -m http.server 8000` na pasta e acesse `http://localhost:8000/comunismo-shorts/`.

Clique em **▶ Iniciar Animação**. O clique é necessário para o navegador liberar o áudio. Teclas: `Espaço` ou `R` reiniciam a animação.

## Gerar o arquivo de vídeo

O botão **⏺ Gravar vídeo** reinicia a animação, grava o canvas a 60 fps junto com os efeitos sonoros (MediaRecorder) e, ao final dos 48 s, baixa o arquivo `comunismo-shorts-1080x1920.webm`. No Chrome, o resultado é VP9 + Opus.

Para converter em MP4 (H.264/AAC) antes de subir:

```bash
ffmpeg -i comunismo-shorts-1080x1920.webm -r 60 -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac -b:a 192k comunismo-shorts.mp4
```

A narração gravada entra no arquivo. A opção "Voz do navegador" não entra, porque o navegador não permite capturar a saída da Web Speech API.

Para gerar uma miniatura ou um quadro estático de qualquer momento, abra `index.html#t=2.3` (o número é o tempo em segundos). No console do navegador, `renderAt(t)` desenha o quadro do tempo `t`.

## Narração e tempos das cenas

O texto da Cena 1 tem 26 palavras, e falar tudo em 4 segundos exigiria uma voz duas vezes mais rápida que o normal. Por isso a narração tem um ritmo único para o vídeo todo (cerca de 1,25× a fala natural), e as cenas seguem a voz, mantendo o total de 48 s:

| Cena | Roteiro original | Com narração |
|---|---|---|
| 1. O gancho | 00–04 s | 00,0–07,2 s |
| 2. Mais-valia | 04–12 s | 07,2–15,3 s |
| 3. Propriedade coletiva | 12–22 s | 15,3–23,7 s |
| 4. Transição socialista | 22–32 s | 23,7–32,3 s |
| 5. A regra de ouro | 32–42 s | 32,3–40,8 s |
| 6. Teoria vs. realidade | 42–48 s | 40,8–48,0 s |

As animações foram coreografadas sobre os tempos do roteiro original. Com a narração, cada cena é ajustada palavra por palavra, então cada efeito acontece na palavra falada correspondente. Sem a narração embutida (`const NARRATION = null`), o vídeo volta aos tempos originais.

Para regerar a voz (por exemplo, depois de mudar um texto em `SCENES`), use `tools/gerar_narracao.py`. Ele usa o [Piper](https://github.com/OHF-Voice/piper1-gpl), um TTS de código aberto que roda offline, com a voz `pt_BR-faber-medium`:

```bash
python3 -m venv .venv && .venv/bin/pip install piper-tts
# baixe pt_BR-faber-medium.onnx e .onnx.json de
# https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium
.venv/bin/python tools/gerar_narracao.py --voz pt_BR-faber-medium.onnx
```

O script ajusta a velocidade para caber em 48 s, estima o tempo de cada palavra pelas pausas da fala e grava tudo dentro do `index.html`. Precisa do `ffmpeg` instalado. Antes de monetizar o vídeo, confira a licença da voz no cartão do modelo.

## Roteiro visual

| Tempo (roteiro) | Cena | Destaques visuais |
|---|---|---|
| 00–04 s | O gancho | Bonequinho com escova de dentes e carro; uma mão gigante tenta tomar tudo; um X vermelho trava a tela com alerta piscando; a mão vai para a fábrica |
| 04–12 s | Meios de produção e mais-valia | Fábrica com engrenagens girando, Karl Marx de lupa, 10 operários produzem 100 caixas, o patrão de cartola fica com 90 e a base fica com 10 |
| 12–22 s | Propriedade privada vs. coletiva | Raio-X apaga a cartola e o cadeado privado; um cadeado coletivo brilhante liga linhas de energia a todos; cartões de terras, minas e indústrias |
| 22–32 s | Transição socialista | Linha do tempo, relógio "não é da noite pro dia", o prédio "ESTADO" cresce, flexiona os músculos e controla os operários como marionetes, a pirâmide de classes se achata, o Estado encolhe (screen shake) e some, deixando uma rede horizontal |
| 32–42 s | A regra de ouro | Moedas evaporam; selos "sem dinheiro / sem patrão / sem governo"; balança dinâmica entre capacidade e necessidade; caixas de saúde, comida e moradia vão para quem precisa |
| 42–48 s | Teoria vs. realidade e loop | Bandeiras do séc. XX (URSS, China, Cuba, Vietnã) travadas na barreira do "Estado gigante" com alerta; depois a câmera volta rapidamente ao bonequinho com a escova de dentes |

## Onde mexer no código

O `index.html` está dividido em 7 seções comentadas:

1. Configuração, easing e roteiro (`SCENES`): texto e timestamps de cada cena, narração embutida (`NARRATION`) e ajuste de tempo palavra por palavra
2. Áudio sintético (`AU`) e voz do navegador (`Voice`); a voz gravada (`Narr`) fica no motor, seção 7
3. Primitivas de desenho e bonequinhos palito (`stick`, rostos, cartola, capacete, barba do Marx, ferramentas)
4. Objetos (fábrica, engrenagens, pirâmide, cadeado, prédio do Estado, balança, bandeiras...)
5. Cenas 1–3 (`sceneN` desenha a cena, `camN` define a câmera virtual)
6. Cenas 4–6
7. Motor: screen shake (`SHAKES`), transições (`CUTS`), legendas, lista de efeitos sonoros (`CUES`), batida, loop principal e gravação
