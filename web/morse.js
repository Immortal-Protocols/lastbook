/* Morse practice page: encode text and play ITU tones with Web Audio. Offline. No network.
   The letter table must stay in lockstep with engine/morse.py (tests compare them).
   Decode from a microphone, a recording, or a light is not in this build. */
'use strict';
const MorsePage = (() => {
  const LETTERS = {
  "A": ".-",
  "B": "-...",
  "C": "-.-.",
  "D": "-..",
  "E": ".",
  "F": "..-.",
  "G": "--.",
  "H": "....",
  "I": "..",
  "J": ".---",
  "K": "-.-",
  "L": ".-..",
  "M": "--",
  "N": "-.",
  "O": "---",
  "P": ".--.",
  "Q": "--.-",
  "R": ".-.",
  "S": "...",
  "T": "-",
  "U": "..-",
  "V": "...-",
  "W": ".--",
  "X": "-..-",
  "Y": "-.--",
  "Z": "--..",
  "0": "-----",
  "1": ".----",
  "2": "..---",
  "3": "...--",
  "4": "....-",
  "5": ".....",
  "6": "-....",
  "7": "--...",
  "8": "---..",
  "9": "----."
};
  const PROSIGNS = {
  "SOS": "...---...",
  "AR": ".-.-.",
  "SK": "...-.-",
  "BT": "-...-",
  "KN": "-.--.",
  "AS": ".-...",
  "HH": "........"
};
  const UNIT_FROM_WPM = wpm => 1.2 / wpm; // PARIS standard, seconds per unit

  function normalizeChar(ch) {
    const map = { '‘': "'", '’': "'", '“': '"', '”': '"', '‐': '-', '‑': '-', '‒': '-', '–': '-', '—': '-', '−': '-' };
    return (map[ch] || ch).toUpperCase();
  }

  function encode(text) {
    const skipped = [];
    const words = [];
    let current = [];
    const raw = String(text || '');
    const upper = raw.toUpperCase();
    const names = Object.keys(PROSIGNS).sort((a, b) => b.length - a.length);
    let i = 0;
    const flush = () => { if (current.length) { words.push(current); current = []; } };
    while (i < raw.length) {
      const ch = raw[i];
      if (/\s/.test(ch)) { flush(); i++; continue; }
      let hit = null;
      for (const name of names) {
        if (upper.startsWith(name, i)) {
          const end = i + name.length;
          const before = i === 0 || /\s/.test(raw[i - 1]);
          const after = end === raw.length || /\s/.test(raw[end]);
          if (before && after) { hit = name; break; }
        }
      }
      if (hit) { current.push(PROSIGNS[hit]); i += hit.length; continue; }
      const n = normalizeChar(ch);
      const sign = LETTERS[n];
      if (!sign) { skipped.push(ch); i++; continue; }
      current.push(sign);
      i++;
    }
    flush();
    const morse = words.map(w => w.join(' ')).filter(Boolean).join(' / ');
    const whole = raw.trim().toUpperCase();
    return {
      text: raw,
      morse,
      prosign: Object.prototype.hasOwnProperty.call(PROSIGNS, whole) && !skipped.length && words.length === 1 && words[0].length === 1,
      skipped,
    };
  }

  function timings(text, wpm) {
    const unit = UNIT_FROM_WPM(wpm) * 1000;
    const marks = encode(text).morse;
    const seq = [];
    const add = (kind, units, mark) => {
      if (units <= 0) return;
      if (kind === 'gap' && seq.length && seq[seq.length - 1].kind === 'gap') {
        seq[seq.length - 1].units += units;
        seq[seq.length - 1].ms = Math.round(unit * seq[seq.length - 1].units);
        return;
      }
      const item = { kind, units, ms: Math.round(unit * units) };
      if (mark) item.mark = mark;
      seq.push(item);
    };
    if (!marks) return seq;
    const parts = marks.split(' / ');
    parts.forEach((word, wi) => {
      const letters = word.split(' ');
      letters.forEach((letter, li) => {
        [...letter].forEach((mark, mi) => {
          if (mark === '.') add('tone', 1, '.');
          else if (mark === '-') add('tone', 3, '-');
          if (mi < letter.length - 1) add('gap', 1);
        });
        if (li < letters.length - 1) add('gap', 3);
      });
      if (wi < parts.length - 1) add('gap', 7);
    });
    return seq;
  }

  let audio, playing = false, timer = 0;

  function stop() {
    playing = false;
    if (timer) { clearTimeout(timer); timer = 0; }
    if (audio) { try { audio.close(); } catch {} audio = null; }
    const btn = document.getElementById('morsePlay');
    if (btn) { btn.textContent = 'Play tones'; btn.setAttribute('aria-pressed', 'false'); }
  }

  function play(text, wpm, freq) {
    stop();
    const seq = timings(text, wpm);
    if (!seq.length) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    audio = new AC();
    playing = true;
    const btn = document.getElementById('morsePlay');
    if (btn) { btn.textContent = 'Stop'; btn.setAttribute('aria-pressed', 'true'); }
    const startAt = audio.currentTime + 0.05;
    let t = startAt;
    const gain = audio.createGain();
    gain.gain.value = 0;
    gain.connect(audio.destination);
    const osc = audio.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = freq;
    osc.connect(gain);
    osc.start(startAt);
    seq.forEach(item => {
      const dur = item.ms / 1000;
      if (item.kind === 'tone') {
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.18, t + 0.008);
        gain.gain.setValueAtTime(0.18, t + dur - 0.008);
        gain.gain.linearRampToValueAtTime(0, t + dur);
      }
      t += dur;
    });
    osc.stop(t + 0.02);
    const ms = Math.max(0, (t - startAt) * 1000) + 40;
    timer = setTimeout(() => stop(), ms);
  }

  function renderTable() {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').map(c => `<span class="morse-cell"><b>${c}</b> <code>${LETTERS[c]}</code></span>`).join('');
    const figs = '0123456789'.split('').map(c => `<span class="morse-cell"><b>${c}</b> <code>${LETTERS[c]}</code></span>`).join('');
    return `<div class="morse-grid" aria-label="ITU Morse letters">${letters}</div>
      <div class="morse-grid" aria-label="ITU Morse figures">${figs}</div>`;
  }

  function page(main) {
    stop();
    setTitle('Morse practice');
    main.innerHTML = `
      <div class="ghero" style="--tc:#00796b"><div class="ghero-in">
        ${crumbs([['Guides', '#/guides'], ['Contact & find way', '#/t/comms'], ['Morse practice']])}
        <div class="row1"><span class="ico">${ico('comms')}</span><h1>Morse practice</h1></div>
        <p class="lead">Encode text as International Morse and play the tones on this device. Nothing is sent anywhere. Decoding Morse from a microphone, a recording, or a light is not in this build.</p>
      </div></div>
      <div class="morse-page">
        <label class="sr" for="morseIn">Text to encode</label>
        <textarea id="morseIn" rows="3" maxlength="500" placeholder="Type a message, a call sign, or SOS">SOS</textarea>
        <div class="morse-out" aria-live="polite">
          <p class="muted small" id="morseMeta"></p>
          <p class="morse-marks" id="morseMarks"></p>
        </div>
        <div class="field morse-controls">
          <label>Speed <input id="morseWpm" type="range" min="5" max="30" value="18" step="1"> <span id="morseWpmN">18</span> WPM</label>
          <label>Tone <input id="morseHz" type="range" min="400" max="900" value="600" step="10"> <span id="morseHzN">600</span> Hz</label>
        </div>
        <div class="vactions">
          <button class="btn" type="button" id="morsePlay">Play tones</button>
          <button class="btn plain" type="button" id="morseStop">Stop</button>
        </div>
        <p class="muted small">SOS as a distress signal is sent as one sign with no letter spaces: <code>...---...</code>. Timing follows the PARIS standard (ITU). A dit is one unit, a dah is three, letter gaps are three, word gaps are seven.</p>
        <h2>ITU letters and figures</h2>
        ${renderTable()}
      </div>`;
    const input = $('#morseIn'), marks = $('#morseMarks'), meta = $('#morseMeta');
    const wpmEl = $('#morseWpm'), hzEl = $('#morseHz');
    const paint = () => {
      const coded = encode(input.value);
      marks.textContent = coded.morse || 'Nothing to encode.';
      const skip = coded.skipped.length ? ` Skipped: ${coded.skipped.join(' ')}.` : '';
      const kind = coded.prosign ? (input.value.trim().toUpperCase() === 'SOS' ? 'Distress prosign.' : 'Prosign.') : '';
      meta.textContent = `${kind}${skip}`.trim();
    };
    const wpmLab = $('#morseWpmN'), hzLab = $('#morseHzN');
    wpmEl.addEventListener('input', () => { wpmLab.textContent = wpmEl.value; });
    hzEl.addEventListener('input', () => { hzLab.textContent = hzEl.value; });
    input.addEventListener('input', paint);
    $('#morsePlay').addEventListener('click', () => {
      if (playing) { stop(); return; }
      play(input.value, +wpmEl.value || 18, +hzEl.value || 600);
    });
    $('#morseStop').addEventListener('click', stop);
    paint();
    leaving = stop;
  }

  return { page, encode, timings, LETTERS, PROSIGNS, stop };
})();
