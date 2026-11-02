# Como nasce um pneu — vídeo vertical em Canvas

Animação vertical estilo Shorts/TikTok (9:16, 1080×1920, 48 s) sobre como um pneu é fabricado. Tudo fica num único `index.html`: desenhos vetoriais em Canvas, legendas palavra por palavra, efeitos sonoros sintetizados com Web Audio API e narração opcional com Web Speech API. Não usa imagens nem arquivos de áudio.

## Como abrir

Abra o arquivo direto no navegador:

```bash
# Linux
xdg-open pneu-shorts/index.html
# macOS
open pneu-shorts/index.html
# Windows (PowerShell)
start pneu-shorts\index.html
```

Ou sirva a pasta localmente:

```bash
python3 -m http.server 8000
# depois acesse http://localhost:8000/pneu-shorts/
```

Clique em **Iniciar Animação** para liberar o áudio do navegador.

## Controles

| Tecla / botão | Ação |
| --- | --- |
| Espaço / Pausar | Pausa e continua |
| R / Reiniciar | Volta para 0 s |
| M / Som | Liga e desliga todo o áudio |
| V / Voz | Liga e desliga a narração sintetizada (pt-BR) |
| Escuro | Alterna o fundo entre #FAF8F5 e #121212 |
| Gravar .webm | Grava os 48 s com os efeitos sonoros e baixa `como-nasce-um-pneu.webm` |

A narração usa as vozes instaladas no sistema. A gravação captura o canvas a 60 fps e os efeitos da Web Audio API, mas não a voz da Web Speech API (os navegadores não expõem esse áudio). Para publicar com narração, grave a voz à parte ou use a gravação de tela do sistema.

## Roteiro e sincronização

| Tempo | Cena | O que acontece |
| --- | --- | --- |
| 00–04 s | O gancho | Carro a 120 km/h, zoom brusco na roda, alerta vermelho, pneu derretendo, caldeirão da "receita" |
| 04–12 s | A receita química | Bonequinho de óculos joga látex, petróleo, sílica, negro de fumo e enxofre no misturador, que treme a tela |
| 12–22 s | Esqueleto de aço e tecido | Raio-X das calandras prensando borracha, cabos de aço e nylon; peso de 10 t testa o tapete |
| 22–32 s | Tambor de montagem | Braços robóticos aplicam 20 camadas, aros de aço entram, a bolsa de ar infla e surge o pneu verde |
| 32–42 s | Vulcanização | Molde segmentado fecha, vapor, termômetro a 170 °C, ligações de enxofre entre moléculas, sulcos esculpidos |
| 42–48 s | Teste e loop | Laser verde caça bolhas, carimbo APROVADO, o pneu pula para o carro da cena 1 e o vídeo recomeça |

Cada palavra da legenda recebe um instante calculado a partir da duração da cena, com peso pelo tamanho da palavra e pausa após pontuação. Animações e sons são presos a palavras-chave (`wt(cena, 'palavra')`), então mudar o texto de uma cena move junto os efeitos ligados a ela. No console, `renderAt(12.5)` desenha qualquer instante para inspeção.
