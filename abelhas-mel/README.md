# Mel em 48 Segundos

Vídeo vertical no estilo "animação viral minimalista" (bonecos palito e vetores 2D) explicando como as abelhas produzem mel. Tudo fica em um único `index.html`: HTML5 Canvas + JavaScript puro, sem dependências nem arquivos de mídia.

- Formato: 9:16, 1080×1920, 60 fps, 48 s (o fim emenda no começo para o loop do TikTok/Shorts)
- Legendas palavra por palavra (palavra atual em amarelo), sincronizadas por timestamp
- Efeitos sonoros e trilha sintetizados com Web Audio API (pops, swooshes, bipes de alerta, líquido, zumbido, carimbo)
- Narração opcional com a voz do navegador (Web Speech API)
- Câmera virtual com zoom, pan e screen shake; entradas elásticas a cada 2–3 s

## Como abrir

Abra o arquivo direto no navegador (Chrome ou Edge recomendados):

```bash
# macOS
open abelhas-mel/index.html
# Linux
xdg-open abelhas-mel/index.html
# Windows (PowerShell ou cmd)
start abelhas-mel\index.html
```

Se preferir servir por HTTP: `python3 -m http.server 8000` na raiz do repositório e acesse `http://localhost:8000/abelhas-mel/`.

Clique em **Iniciar Animação**: o clique libera o áudio do navegador e começa a reprodução.

## Controles

| Tecla | Ação |
| --- | --- |
| Espaço | Pausar / continuar |
| R | Reiniciar |
| ← / → | Voltar / avançar 2 s |
| F | Tela cheia |
| L | Liga/desliga o loop |

Na tela inicial dá para ligar ou desligar narração, trilha e loop, e escolher o fundo (`#FAF8F5` ou `#121212`).

Parâmetros de URL úteis: `?t=12.5` mostra o quadro exato daquele segundo (bom para thumbnail) e `?bg=dark` abre com fundo escuro.

## Exportar o vídeo

O botão **Exportar vídeo 60 fps** renderiza os 2880 quadros em tempos exatos (t = i/60), sintetiza o áudio num `OfflineAudioContext` e baixa um `.webm` (VP9 + Opus). Como não depende da velocidade da máquina, o arquivo sai sempre com 60 fps cheios. Requer WebCodecs (Chrome/Edge 94+, Firefox 130+); em navegadores sem WebCodecs o botão vira **Gravar em tempo real** (MediaRecorder).

Para MP4 (Instagram, TikTok):

```bash
ffmpeg -i como-as-abelhas-fazem-mel-1080x1920-60fps.webm -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac video.mp4
```

A narração da Web Speech API toca ao vivo, mas o navegador não permite capturá-la: o arquivo exportado leva trilha e efeitos. Para ter voz no vídeo final, grave a narração por cima na edição.

## Roteiro e tempos

| Tempo | Cena | O que acontece |
| --- | --- | --- |
| 0–4 s | O Gancho | Boneco comendo torrada com mel; zoom na colher com alerta vermelho |
| 4–12 s | A Coleta | Abelha de capacete pousa na flor; barra lateral 0→100%; balança abelha × néctar |
| 12–22 s | Os Dois Estômagos | Scanner de raio-X; papo de mel, estômago e válvula; enzimas-tesoura cortam a sacarose |
| 22–32 s | O Telefone sem Fio | Três abelhas passam a gota de boca em boca; medidor de água cai de 70% para 30% |
| 32–42 s | Secagem Industrial | Gota no hexágono; abelhas ventilando, vento, vapor e termômetro a 35 °C |
| 42–48 s | O Lacre e Loop | Umidade em 18%, tampa de cera, carimbo "Validade: Eterna" e volta ao boneco |

## Como o código está organizado

`render(T)` é uma função pura do tempo: o mesmo `T` sempre gera o mesmo quadro. Por isso pausar, buscar, repetir em loop e exportar quadro a quadro mantêm tudo sincronizado. Seções do script, na ordem:

1. Utilidades, easings (elastic, bounce, back) e paletas
2. Áudio: síntese dos efeitos, trilha a 120 BPM (24 compassos = 48 s) e agendador com lookahead
3. Roteiro: tempo de cada palavra (proporcional às sílabas), páginas de legenda e narrador
4. Primitivas de desenho: boneco palito com IK, abelha geométrica, flor, favos, medidores, carimbo
5. Câmera virtual e as 6 cenas
6. Transições, reprodução, exportação (WebCodecs + muxer WebM) e controles
