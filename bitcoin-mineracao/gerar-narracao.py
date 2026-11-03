#!/usr/bin/env python3
"""
Gera a narração com voz neural (Kokoro-82M, licença Apache-2.0) e a embute no index.html.

1. Lê o texto de cada cena do array SCENES do index.html.
2. Sintetiza cada cena com o Kokoro (voz pt-BR) e ajusta a velocidade para o total ficar ~48s.
3. Mede o instante exato de cada palavra com o Whisper (faster-whisper); sem ele, distribui por sílabas.
4. Monta uma trilha única (MP3) e grava no index.html, entre os marcadores NARRACAO_INICIO/FIM:
   o áudio em base64 + os tempos de cena e de cada palavra. O vídeo inteiro (cenas, legendas e
   efeitos) se re-sincroniza a partir desses tempos.

Requisitos: pip install kokoro-onnx soundfile numpy faster-whisper  (+ ffmpeg no PATH)
Modelos:    kokoro-v1.0.onnx e voices-v1.0.bin de
            https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
Uso:        python3 gerar-narracao.py --modelos ./modelos [--voz pm_alex] [--duracao 48]
Vozes pt-BR: pm_alex (masculina), pm_santa (masculina), pf_dora (feminina)
"""
import argparse, base64, difflib, json, os, re, subprocess, sys, tempfile, unicodedata
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 24000
LEAD, GAP, TAIL = 0.12, 0.32, 0.12          # silêncio antes da 1ª fala, entre cenas e no final


def norm(w):
    w = unicodedata.normalize('NFD', w.lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', w)


def read_scenes(html):
    block = html[html.index('const SCENES = ['):html.index('];', html.index('const SCENES = ['))]
    return re.findall(r"text:'([^']+)'", block)


def trim(a, thr=0.006):
    # remove silêncio nas pontas, preservando o ataque de consoantes suaves (m, n, v…)
    idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - int(0.09 * SR)):min(len(a), idx[-1] + int(0.08 * SR))] if len(idx) else a


def synth(k, text, voice, speed):
    # a vírgula inicial dá ao modelo um "respiro" e evita engolir a 1ª consoante da frase
    s, sr = k.create(', ' + text, voice=voice, speed=speed, lang='pt-br')
    assert sr == SR
    return trim(np.asarray(s, dtype=np.float32))


def syllables(w):
    return max(1, len(re.findall(r'[aeiouáéíóúâêôãõà]+', w.lower())))


def word_times(audio, words, whisper):
    """[t0, t1] (s, relativos ao início do áudio da cena) para cada palavra do roteiro."""
    dur = len(audio) / SR
    est = None
    if whisper is not None:
        a16 = np.interp(np.arange(0, len(audio), SR / 16000), np.arange(len(audio)), audio).astype(np.float32)
        segs, _ = whisper.transcribe(a16, language='pt', word_timestamps=True, beam_size=5, initial_prompt=' '.join(words))
        hyp = [(norm(w.word), w.start, w.end) for s in segs for w in s.words if norm(w.word)]
        ref = [norm(w) for w in words]
        est = [None] * len(words)
        sm = difflib.SequenceMatcher(None, ref, [h[0] for h in hyp], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for d in range(i2 - i1): est[i1 + d] = [hyp[j1 + d][1], hyp[j1 + d][2]]
            elif tag == 'replace' and j2 > j1:          # palavras fundidas/separadas: reparte o trecho
                t0, t1 = hyp[j1][1], hyp[j2 - 1][2]
                tot = sum(syllables(w) for w in words[i1:i2]); acc = t0
                for d in range(i2 - i1):
                    dd = (t1 - t0) * syllables(words[i1 + d]) / tot
                    est[i1 + d] = [acc, acc + dd]; acc += dd
    if est is None or all(e is None for e in est):
        est = [None] * len(words)
    # interpola o que faltou (ou tudo, sem Whisper) proporcionalmente às sílabas
    i = 0
    while i < len(words):
        if est[i] is not None: i += 1; continue
        j = i
        while j < len(words) and est[j] is None: j += 1
        a = est[i - 1][1] if i > 0 else 0.0
        b = est[j][0] if j < len(words) else dur
        tot = sum(syllables(w) for w in words[i:j]); acc = a
        for d in range(i, j):
            dd = (b - a) * syllables(words[d]) / tot
            est[d] = [acc, acc + dd]; acc += dd
        i = j
    for d in range(1, len(est)):                         # monotonicidade
        est[d][0] = max(est[d][0], est[d - 1][0] + 0.02); est[d][1] = max(est[d][1], est[d][0] + 0.05)
    return [[round(a, 3), round(b, 3)] for a, b in est]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelos', default=os.path.join(HERE, 'modelos'))
    ap.add_argument('--voz', default='pm_alex')
    ap.add_argument('--duracao', type=float, default=49.5, help='duração total desejada (45–50s)')
    ap.add_argument('--html', default=os.path.join(HERE, 'index.html'))
    ap.add_argument('--sem-whisper', action='store_true')
    a = ap.parse_args()

    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(a.modelos, 'kokoro-v1.0.onnx'), os.path.join(a.modelos, 'voices-v1.0.bin'))
    html = open(a.html, encoding='utf-8').read()
    texts = read_scenes(html)
    print(f'{len(texts)} cenas, voz {a.voz}')

    # 1ª passada em velocidade 1.0 para medir; depois ajusta a velocidade para caber na duração alvo
    budget = a.duracao - LEAD - TAIL - GAP * (len(texts) - 1)
    speed, clips = 1.0, None
    for it in range(5):                    # a velocidade do Kokoro não é linear: calibra em algumas passadas
        clips = [synth(k, t, a.voz, speed) for t in texts]
        total = sum(len(c) for c in clips) / SR
        print(f'  passada {it + 1}: velocidade {speed:.3f} → fala {total:.2f}s (alvo {budget:.2f}s)')
        if abs(total - budget) < 0.2 or (speed >= 1.4 and total > budget): break
        speed = float(np.clip(speed * (total / budget) ** 1.4, 0.9, 1.4))

    whisper = None
    if not a.sem_whisper:
        try:
            from faster_whisper import WhisperModel
            whisper = WhisperModel('small', device='cpu', compute_type='int8')
        except Exception as e:
            print('Whisper indisponível, usando estimativa por sílabas:', e)

    scenes, track, t = [], [np.zeros(int(LEAD * SR), np.float32)], LEAD
    for i, (txt, clip) in enumerate(zip(texts, clips)):
        words = txt.split()
        wt = word_times(clip, words, whisper)
        start = 0.0 if i == 0 else t - GAP / 2
        scenes.append({'start': round(start, 3), 'voice': round(t, 3), 'words': [[round(t + w0, 3), round(t + w1, 3)] for w0, w1 in wt]})
        track.append(clip); t += len(clip) / SR
        if i < len(texts) - 1:
            track.append(np.zeros(int(GAP * SR), np.float32)); t += GAP
    total = round(t + TAIL, 3)
    for i, s in enumerate(scenes): s['end'] = scenes[i + 1]['start'] if i + 1 < len(scenes) else total
    audio = np.concatenate(track + [np.zeros(int(TAIL * SR), np.float32)])
    audio = audio / max(1e-6, np.abs(audio).max()) * 0.89

    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = os.path.join(tmp, 'n.wav'), os.path.join(tmp, 'n.mp3')
        sf.write(wav, audio, SR)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-af', 'highpass=f=70,acompressor=threshold=-18dB:ratio=2.5:attack=5:release=80',
                        '-ac', '1', '-ar', '24000', '-c:a', 'libmp3lame', '-b:a', '64k', mp3], check=True)
        b64 = base64.b64encode(open(mp3, 'rb').read()).decode()
        sf.write(os.path.join(HERE, 'narracao-preview.wav'), audio, SR) if os.environ.get('SALVAR_WAV') else None

    data = {'voz': a.voz, 'motor': 'Kokoro-82M', 'velocidade': round(speed, 3), 'duracao': total, 'cenas': scenes}
    block = ('/*NARRACAO_INICIO*/\nconst NARRATION = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) +
             ';\nconst NARRATION_AUDIO = "data:audio/mpeg;base64,' + b64 + '";\n/*NARRACAO_FIM*/')
    i0, i1 = html.find('/*NARRACAO_INICIO*/'), html.find('/*NARRACAO_FIM*/')
    if i0 < 0 or i1 < 0: sys.exit('Marcadores NARRACAO_INICIO/FIM não encontrados no index.html')
    html = html[:i0] + block + html[i1 + len('/*NARRACAO_FIM*/'):]
    open(a.html, 'w', encoding='utf-8').write(html)
    print(f'Narração embutida: {total:.2f}s, {len(b64) // 1024} KB em base64')
    for i, s in enumerate(scenes): print(f'  cena {i + 1}: {s["start"]:6.2f}s – {s["end"]:6.2f}s')


if __name__ == '__main__':
    main()
