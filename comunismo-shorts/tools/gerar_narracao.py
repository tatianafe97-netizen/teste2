#!/usr/bin/env python3
"""Gera a narração do vídeo e embute o áudio + os tempos de cada palavra no index.html.

Usa o Piper (TTS neural de código aberto, roda offline) com uma voz pt-BR.

    python -m venv .venv && .venv/bin/pip install piper-tts
    # baixe a voz (2 arquivos) de https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium
    .venv/bin/python tools/gerar_narracao.py --voz caminho/pt_BR-faber-medium.onnx

O script:
  1. lê os textos das 6 cenas direto do index.html;
  2. sintetiza cada cena e ajusta a velocidade da voz para o total caber em 48 s;
  3. detecta as pausas da fala para estimar o tempo de cada palavra (legendas sincronizadas);
  4. concatena tudo numa trilha de 48 s, codifica em MP3 (ffmpeg) e grava em
     `const NARRATION = ...; /* narracao-gerada */` dentro do index.html.
"""
import argparse, base64, io, json, os, re, subprocess, tempfile, wave
import numpy as np
from piper import PiperVoice, SynthesisConfig

DURACAO = 48.0
LEAD = 0.10       # silêncio antes da fala, no início de cada cena
RESPIRO = 0.22    # pausa entre o fim de uma cena e o início da próxima
CAUDA = 0.75      # tempo final para o zoom de volta ao gancho (loop)
PONTUACAO = re.compile(r"[,:;.!?…]$")


def ler_cenas(html):
    bloco = html[html.index("const SCENES = ["):html.index("];", html.index("const SCENES = ["))]
    return re.findall(r"text: '([^']*)'", bloco)


def sintetizar(voz, texto, escala):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voz.synthesize_wav(texto, w, syn_config=SynthesisConfig(length_scale=escala))
    buf.seek(0)
    with wave.open(buf) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a, sr


def rms_quadros(a, sr, passo=0.01):
    n = int(sr * passo)
    k = len(a) // n
    return np.sqrt((a[: k * n].reshape(k, n) ** 2).mean(axis=1)), n


def aparar(a, sr):
    r, n = rms_quadros(a, sr)
    lim = 0.05 * np.percentile(r, 95)
    voz = np.where(r > lim)[0]
    return a[max(0, voz[0] * n - n): min(len(a), (voz[-1] + 2) * n)]


def tempos_palavras(a, sr, texto):
    """Tempo (s) de início de cada palavra, relativo ao começo do trecho aparado."""
    palavras = texto.split()
    r, n = rms_quadros(a, sr)
    lim = 0.06 * np.percentile(r, 95)
    silencio = r < lim
    pausas, i = [], 0
    while i < len(r):
        if silencio[i]:
            j = i
            while j < len(r) and silencio[j]:
                j += 1
            if i > 0 and j < len(r) and (j - i) >= 7:
                pausas.append((i * n / sr, j * n / sr))
            i = j
        else:
            i += 1
    quebras = [k for k, p in enumerate(palavras[:-1]) if PONTUACAO.search(p)]
    total = len(a) / sr
    if len(pausas) >= len(quebras):
        pausas = sorted(sorted(pausas, key=lambda p: p[1] - p[0], reverse=True)[: len(quebras)])
    else:
        quebras, pausas = [], []
    # trechos de fala entre as pausas, cada um com seu grupo de palavras
    limites = [0.0] + [x for p in pausas for x in p] + [total]
    trechos = [(limites[2 * k], limites[2 * k + 1]) for k in range(len(pausas) + 1)]
    grupos, ini = [], 0
    for q in quebras + [len(palavras) - 1]:
        grupos.append(palavras[ini: q + 1])
        ini = q + 1
    inicios = []
    for (s, e), g in zip(trechos, grupos):
        pesos = [len(re.sub(r"[^\w]", "", w)) + 1.5 for w in g]
        acc = 0.0
        for p in pesos:
            inicios.append(s + (e - s) * acc / sum(pesos))
            acc += p
    return palavras, inicios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", required=True, help="arquivo .onnx da voz Piper (o .onnx.json deve estar ao lado)")
    ap.add_argument("--html", default=os.path.join(os.path.dirname(__file__), "..", "index.html"))
    args = ap.parse_args()

    html = open(args.html, encoding="utf-8").read()
    textos = ler_cenas(html)
    voz = PiperVoice.load(args.voz)
    alvo = DURACAO - LEAD - (len(textos) - 1) * (RESPIRO + LEAD) - CAUDA

    escala = 1.0
    for _ in range(4):  # ajusta a velocidade até o total caber em 48 s
        brutos = [sintetizar(voz, t, escala) for t in textos]
        sr = brutos[0][1]
        trechos = [aparar(a, sr) for a, _ in brutos]
        fala = sum(len(t) for t in trechos) / sr
        if fala <= alvo and fala > alvo - 0.4:
            break
        escala *= (alvo - 0.15) / fala

    trilha, cenas, cursor = [], [], 0.0
    for i, (texto, a) in enumerate(zip(textos, trechos)):
        inicio = 0.0 if i == 0 else cursor + RESPIRO
        fala_ini = inicio + LEAD
        palavras, inicios = tempos_palavras(a, sr, texto)
        fala_fim = fala_ini + len(a) / sr
        abs_ini = [fala_ini + s for s in inicios]
        words = [{"w": w, "s": round(s, 3), "e": round(abs_ini[k + 1] if k + 1 < len(abs_ini) else fala_fim + .25, 3)}
                 for k, (w, s) in enumerate(zip(palavras, abs_ini))]
        cenas.append({"start": round(inicio, 3), "words": words})
        ja = sum(len(x) for x in trilha)  # amostras já escritas
        trilha.append(np.zeros(max(0, int(round(fala_ini * sr)) - ja), np.float32))
        trilha.append(a)
        cursor = fala_fim
    for i, c in enumerate(cenas):
        c["end"] = cenas[i + 1]["start"] if i + 1 < len(cenas) else DURACAO
    audio = np.concatenate(trilha)
    audio = np.concatenate([audio, np.zeros(int(DURACAO * sr) - len(audio), np.float32)])
    audio = audio / max(1e-6, np.abs(audio).max()) * 0.89

    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = os.path.join(tmp, "n.wav"), os.path.join(tmp, "n.mp3")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes((audio * 32767).astype(np.int16).tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-b:a", "64k", mp3], check=True)
        b64 = base64.b64encode(open(mp3, "rb").read()).decode()

    dados = {"duration": DURACAO, "voice": os.path.basename(args.voz), "lengthScale": round(escala, 3), "scenes": cenas, "audio": b64}
    linha = "const NARRATION = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "; /* narracao-gerada */"
    novo, n = re.subn(r"^const NARRATION = .*; /\* narracao-gerada \*/$", lambda m: linha, html, flags=re.M)
    if n != 1:
        raise SystemExit("Marcador 'const NARRATION = ...; /* narracao-gerada */' não encontrado no index.html")
    open(args.html, "w", encoding="utf-8").write(novo)
    print(f"velocidade (length_scale): {escala:.3f}  ·  MP3: {len(b64) * 3 // 4 // 1024} KB")
    for i, c in enumerate(cenas):
        print(f"cena {i + 1}: {c['start']:6.2f}s – {c['end']:6.2f}s  ({len(c['words'])} palavras)")


if __name__ == "__main__":
    main()
