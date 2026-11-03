#!/usr/bin/env node
/*
 * Exportador offline do vídeo "Mineração de Bitcoin" (opcional).
 *
 * Renderiza o index.html quadro a quadro em t = n/60 (2.880 quadros exatos,
 * 1080x1920, 60fps), renderiza a trilha sonora sintética com OfflineAudioContext
 * e junta tudo em um MP4 H.264 + AAC pronto para Shorts/TikTok/Reels.
 * Diferente da gravação em tempo real do navegador, aqui nenhum quadro é perdido,
 * mesmo em máquinas lentas.
 *
 * Requisitos: Node 18+, ffmpeg no PATH e Playwright (npm i playwright && npx playwright install chromium)
 * Uso:        node exportar-video.js [saida.mp4] [--sem-voz] [--sem-batida] [--crf=18]
 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { pathToFileURL } = require('url');

const args = process.argv.slice(2);
const out = path.resolve(args.find(a => !a.startsWith('--')) || 'mineracao-bitcoin-9x16-60fps.mp4');
const music = !args.includes('--sem-batida');
const voice = !args.includes('--sem-voz');
const crf = (args.find(a => a.startsWith('--crf=')) || '--crf=18').split('=')[1];
const page_url = pathToFileURL(path.join(__dirname, 'index.html')).href + '?export=1';

function srtTime(t) {
  const ms = Math.round(t * 1000), h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
}

(async () => {
  const launchOpts = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {};
  const browser = await chromium.launch(launchOpts);
  const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
  page.on('pageerror', e => console.error('Erro na página:', e.message));
  await page.goto(page_url, { waitUntil: 'load' });
  await page.evaluate(async () => {
    try { await Promise.all([document.fonts.load('900 76px Montserrat'), document.fonts.load('800 34px "JetBrains Mono"')]); } catch (e) { }
    await document.fonts.ready;
  });
  const info = await page.evaluate(() => ({ dur: window.__mining.DURATION, fps: window.__mining.FPS }));
  const frames = Math.round(info.dur * info.fps);

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mineracao-'));
  const wav = path.join(tmp, 'trilha.wav');
  process.stdout.write('Renderizando áudio offline… ');
  fs.writeFileSync(wav, Buffer.from(await page.evaluate(([m, v]) => window.__mining.renderAudioOffline(m, v), [music, voice]), 'base64'));
  console.log('ok');

  const srt = out.replace(/\.[^.]+$/, '') + '.srt';
  const pages = await page.evaluate(() => window.__mining.PAGES.map(p => ({ t0: p.t0, t1: p.t1, text: p.words.map(w => w.text).join(' ') })));
  fs.writeFileSync(srt, pages.map((p, i) => `${i + 1}\n${srtTime(p.t0)} --> ${srtTime(p.t1)}\n${p.text}\n`).join('\n'));

  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(info.fps), '-c:v', 'mjpeg', '-i', '-',
    '-i', wav, '-map', '0:v', '-map', '1:a',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', String(info.fps),
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => { ff.on('error', rej); ff.on('close', code => code === 0 ? res() : rej(new Error('ffmpeg saiu com código ' + code))); });

  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    const data = await page.evaluate(t => { window.__mining.render(t); return document.getElementById('c').toDataURL('image/jpeg', 0.95); }, i / info.fps);
    if (!ff.stdin.write(Buffer.from(data.slice(data.indexOf(',') + 1), 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
    if (i % info.fps === 0 || i === frames - 1) process.stdout.write(`\rQuadros: ${i + 1}/${frames}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await done;
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`\nPronto: ${out}\nLegendas: ${srt}`);
})().catch(err => { console.error('\nFalha na exportação:', err.message); process.exit(1); });
