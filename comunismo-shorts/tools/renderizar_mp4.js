#!/usr/bin/env node
/* Exporta o vídeo em MP4 (H.264 + AAC, 1080x1920, 60 fps) quadro a quadro, sem depender de tempo real.
   Requisitos: Node.js, Playwright com Chromium (`npm i playwright && npx playwright install chromium`) e ffmpeg.
   Uso: node tools/renderizar_mp4.js [saida.mp4]                                                        */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');

const FPS = 60;
const html = path.resolve(__dirname, '..', 'index.html');
const saida = path.resolve(process.argv[2] || 'comunismo-shorts-1080x1920.mp4');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('pageerror', e => console.error('Erro na página:', e.message));
  await page.goto('file://' + html + '#t=0');
  await page.evaluate(() => document.fonts.load('900 76px Montserrat').catch(() => {}));
  const dur = await page.evaluate(() => DURATION);

  console.log('Mixando o áudio (voz + efeitos + batida)...');
  const wav = path.join(os.tmpdir(), `trilha-${process.pid}.wav`);
  fs.writeFileSync(wav, Buffer.from(await page.evaluate(() => mixOffline(48000)), 'base64'));

  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-i', wav,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', String(FPS),
    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', saida], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg saiu com código ' + c))));

  const total = Math.round(dur * FPS);
  for (let i = 0; i < total; i++) {
    const b64 = await page.evaluate(t => { renderAt(t); return document.getElementById('cv').toDataURL('image/png').slice(22); }, i / FPS);
    if (!ff.stdin.write(Buffer.from(b64, 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
    if (i % FPS === 0) process.stdout.write(`\rQuadros: ${i}/${total}`);
  }
  ff.stdin.end();
  await done;
  fs.unlinkSync(wav);
  await browser.close();
  console.log(`\rQuadros: ${total}/${total}\nPronto: ${saida}`);
})().catch(e => { console.error(e); process.exit(1); });
