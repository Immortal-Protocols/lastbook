"""Local retrieval service shared by the web app and the assistant.

Keyword search (the library's own FTS5/BM25 index, read only) + meaning-based search (bge-small-en-v1.5 run locally
with onnxruntime, or on a Mac by lastbook-llm --embed) fused with reciprocal-rank fusion. Every passage carries provenance: catalog id, PDF file page or
video timestamp, and which retriever found it.

The semantic index lives in derived/index/ (SSD): semantic.sqlite (chunks, per-document signatures) and vectors.f16
(append-only float16 rows). It grows incrementally: documents whose catalog signature changed or that are new get
(re)embedded; nothing in library-data is written. semantic.sqlite also records what made the vectors (meta 'made_by'),
and meaning search stays off with any other model or settings.
"""
import atexit, hashlib, html, json, math, os, re, sqlite3, subprocess, sys, threading, time, traceback, weakref
from pathlib import Path

import engine.paths as lastbook_paths
from engine.paths import ro_uri
from engine.saved_pages import caption_blocks
HERE = lastbook_paths.DATA  # holds derived/
if not lastbook_paths.FROZEN and os.name != 'nt' and sys.version_info[:2] == (3, 12):  # Mac binaries that belong to the program, built for 3.12, so they would shadow another Python's numpy; never import code from a data folder
    sys.path.insert(0, str(lastbook_paths.APP / 'derived' / 'pylib'))
LIB = lastbook_paths.LIB
IDX = HERE / 'derived' / 'index'
MODEL = HERE / 'derived' / 'models' / 'bge-small-en-v1.5'
DIM = 384
CHUNK, OVERLAP, MINLEN = 1100, 150, 80
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
MAX_TOKENS = 320   # where both engines cut a passage
MODEL_ID = 'bge-small-en-v1.5'
# The index records what made its vectors: another model's vectors, or this model's with other settings, cannot be compared
# with them. A file is known by its SHA-256, so the two forms of bge-small count as one model. A form is listed only after its
# vectors were compared with the other's (#168: cosine 0.998 or more on 10,000 passages). Any other file is named by its own
# SHA-256, so an index it builds works with that file alone.
KNOWN_MODELS = {
    '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35': MODEL_ID,   # model.onnx, BAAI's ONNX export (onnxruntime)
    'bf40c42ad7d89382e9ba7376d5c4b73f6b556cb541fab37aaa1da9c320149b65': MODEL_ID,   # bge-small-en-v1.5-f32.gguf (lastbook-llm --embed)
}

TELEMETRY = 'onnxruntime not loaded'
# This app stays offline. Read when onnxruntime is imported: the Mac build otherwise opens a usage store and connects to
# Microsoft's collector, whatever disable_telemetry_events says. The Windows build has no such switch: see engine/quiet_onnx.py.
os.environ['ORT_DISABLE_TELEMETRY'] = '1'
GGUF = MODEL / 'bge-small-en-v1.5-f32.gguf'   # the same model in the form llama.cpp reads
ENGINE = None   # what makes the vectors: 'llama' (lastbook-llm --embed), 'onnx' (onnxruntime) or None (keyword search only)
RUNNER = None   # lastbook-llm, when ENGINE is 'llama'
# Only a Mac looks for the program for this. LASTBOOK_EMBED_RUNNER=0 turns it off for checks that must run with no model;
# they also block onnxruntime, which the code below would otherwise load when model.onnx is in the library.
if sys.platform == 'darwin' and GGUF.exists() and os.environ.get('LASTBOOK_EMBED_RUNNER') != '0':
    try:
        from llm_local import runner_path
        RUNNER = runner_path()
    except Exception:
        RUNNER = None
try:
    import numpy as np
    if RUNNER:
        ENGINE = 'llama'  # a Mac ships without onnxruntime: the program that runs the local AI makes the vectors, and onnxruntime is never loaded
    AVAILABLE = ENGINE == 'llama' or (MODEL / 'model.onnx').exists()
    if AVAILABLE and not ENGINE:  # with no model there is no reason to load it at all
        if os.name == 'nt':  # before the import, which already writes usage events to Windows. If this fails, the import is not reached.
            from engine import quiet_onnx
            quiet_onnx.silence()
        import onnxruntime as ort
        from tokenizers import Tokenizer
        ENGINE = 'onnx'
        try:
            if hasattr(ort, 'disable_telemetry_events'):
                ort.disable_telemetry_events()
                TELEMETRY = f'ORT_DISABLE_TELEMETRY set, disable_telemetry_events called (onnxruntime {ort.__version__})'
            else:
                TELEMETRY = f'ORT_DISABLE_TELEMETRY set; onnxruntime {ort.__version__} has no disable_telemetry_events'
            if os.name == 'nt':
                TELEMETRY += '; its calls that write events to Windows are replaced before it loads (engine/quiet_onnx.py)'
        except Exception as e:
            TELEMETRY = f'disable_telemetry_events failed: {type(e).__name__}'
except Exception as e:  # semantic search is optional; keyword search keeps working
    AVAILABLE = False
    ENGINE = None
    IMPORT_ERROR = str(e)


class Embedder:
    def __init__(self):
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(2, (os.cpu_count() or 4) // 2)  # leave CPU for the web server and workers
        self.sess = ort.InferenceSession(str(MODEL / 'model.onnx'), so, providers=['CPUExecutionProvider'])
        self.tok = Tokenizer.from_file(str(MODEL / 'tokenizer.json'))
        self.tok.enable_truncation(max_length=MAX_TOKENS)
        self.tok.enable_padding()
        self.inputs = {i.name for i in self.sess.get_inputs()}
        self.lock = threading.Lock()

    def embed(self, texts, search=False, force=False):
        enc = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {'input_ids': ids, 'attention_mask': mask}
        if 'token_type_ids' in self.inputs:
            feed['token_type_ids'] = np.zeros_like(ids)
        with self.lock:
            out = self.sess.run(None, feed)[0]
        v = out[:, 0, :]  # bge uses the [CLS] vector
        if v.shape[1] != DIM:   # another model: its vectors must never reach the index
            raise WrongModel(f'model.onnx gives vectors of {v.shape[1]} numbers; the index needs {DIM}')
        v = v / np.linalg.norm(v, axis=1, keepdims=True).clip(1e-9)
        return v.astype(np.float32)


class RunnerFailed(RuntimeError):
    """lastbook-llm --embed could not be started, stopped, hung, or answered with vectors that cannot be used.
    died: it stopped on its own. resting: it was not even asked (it failed a moment ago, is busy, or Lastbook is closing)."""

    def __init__(self, msg, died=False, resting=False):
        super().__init__(msg)
        self.died, self.resting = died, resting


class WrongModel(RunnerFailed):
    """The model gives vectors of another size or pooling: it is another model, not a passing failure."""


class TextRejected(RuntimeError):
    """lastbook-llm --embed is running but refused the texts of one request. It stays running for the next ones."""


REFUSED = ('bad_request',)   # the one error code about a request's texts. decode (encode in older builds) is the program
                             # or the machine failing (memory, the GPU): like cancel and the rest, it gets the program restarted


class RunnerEmbedder:
    """The same vectors from lastbook-llm --embed (llama.cpp), for a Mac. The program starts at the first text and stays;
    it speaks only through its pipes and leaves when Lastbook closes them.

    Every request has a deadline that covers sending it and reading the answer; past it the program is killed. A program
    that fails to start, hangs or answers badly is not started again for a while (5 s, doubling up to 5 min), so a broken
    one costs each search almost nothing. Every answer is checked: one vector per text, DIM finite numbers each.
    A search that has to start the program first can take up to START_S on top of SEARCH_S."""
    START_S = 20       # longest wait for the program to load the model and say it is ready
    BASE_S = 10        # building the index: longest wait for an answer, this plus PER_TEXT_S for each text
    PER_TEXT_S = 0.5
    SEARCH_S = 5       # a search: longest wait for the answer, and for the program while it works on the index
    RETRY_S = (5, 300)
    LINE_MAX = 64 * 2**20   # longest answer line read; a 48-text answer is about 0.4 MB

    def __init__(self, argv=None):
        self.argv = argv   # None: lastbook-llm with the GGUF. Tests pass a stand-in.
        self.proc, self.next_id, self.starts = None, 0, 0
        self.failures, self.retry_at, self.busy_until, self.closed = 0, 0.0, 0.0, False
        self.lock = threading.Lock()
        me = weakref.ref(self)
        atexit.register(lambda: me() and me().close())

    def _deadline(self, seconds):
        """Kill the program if what follows takes longer than this. Returns the timer, and an Event set when it ran out."""
        proc, fired = self.proc, threading.Event()

        def expire():
            fired.set()
            try:
                proc.kill()
            except OSError:
                pass
        timer = threading.Timer(seconds, expire)
        timer.daemon = True
        timer.start()
        return timer, fired

    def _start(self):
        logs = HERE / 'derived' / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / 'embed.log', 'ab') as err:   # what llama.cpp says while it loads and works, for when something goes wrong
            err.write(f'\n--- {time.strftime("%Y-%m-%d %H:%M:%S")} start\n'.encode())
            err.flush()
            argv = self.argv or [str(RUNNER), '--embed', '--model', str(GGUF)]
            self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
        self.starts += 1
        if self.closed:   # Lastbook began closing while it started
            raise RunnerFailed('Lastbook is closing', resting=True)
        timer, fired = self._deadline(self.START_S)
        try:
            ready = self._read('ready', None, fired)
        finally:
            timer.cancel()
        # The program pools the way the model file says. The index was built with bge's first-token (CLS) vectors of DIM
        # numbers: a file that says otherwise would give vectors of the right size but the wrong meaning. Older builds
        # do not say, and always pooled CLS.
        if ready.get('pooling', 'cls') != 'cls' or ready.get('dim', DIM) != DIM:
            raise WrongModel(f"lastbook-llm loaded a model with {ready.get('pooling')} pooling and {ready.get('dim')} "
                               f'numbers per vector; this index needs cls and {DIM}')

    def _stop(self):
        proc, self.proc = self.proc, None
        if not proc:
            return
        try:
            proc.kill()
            proc.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for f in (proc.stdin, proc.stdout):
            try:
                f.close()
            except OSError:
                pass

    def _read(self, ev, rid, fired):
        while True:
            raw = self.proc.stdout.readline(self.LINE_MAX)
            if not raw:
                break
            if len(raw) >= self.LINE_MAX and not raw.endswith(b'\n'):
                raise RunnerFailed('lastbook-llm answered with a line too long to be an answer')
            try:
                j = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(j, dict):
                continue
            if j.get('ev') == 'error':
                if rid is not None and j.get('id') == rid and j.get('code') in REFUSED:
                    raise TextRejected(f"lastbook-llm refused the texts: {j.get('code')}: {j.get('msg')}")
                raise RunnerFailed(f"lastbook-llm: {j.get('code')}: {j.get('msg')}")
            if j.get('ev') == ev and (rid is None or j.get('id') == rid):
                return j
        if fired.is_set():
            raise RunnerFailed('lastbook-llm did not answer in time')
        raise RunnerFailed('lastbook-llm stopped', died=True)

    def _ask(self, line, rid, n, seconds):
        timer, fired = self._deadline(seconds)   # started before writing: a program that stops reading cannot block us
        try:
            try:
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
            except (OSError, ValueError):
                if fired.is_set():
                    raise RunnerFailed('lastbook-llm did not answer in time') from None
                raise RunnerFailed('lastbook-llm stopped', died=True) from None
            vectors = self._read('embedding', rid, fired).get('vectors')
        finally:
            timer.cancel()
        try:
            v = np.array(vectors, dtype=np.float32)
        except (ValueError, TypeError):
            raise RunnerFailed('lastbook-llm answered with vectors of different sizes') from None
        if v.shape != (n, DIM) or not np.isfinite(v).all():   # another model, or a broken answer: never into the index
            raise RunnerFailed(f'lastbook-llm answered with vectors of shape {v.shape}, not {n} of {DIM} numbers')
        return v

    def embed(self, texts, search=False, force=False):
        """search: a person is waiting, so short limits, and no wait at all just after the program was found busy.
        force: ask even if it failed a moment ago, and do not count a failure (building the index checks with it)."""
        texts = [str(t).encode('utf-8', 'replace').decode('utf-8') for t in texts]   # a lone surrogate would break the request line
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        if search and time.monotonic() < self.busy_until:
            raise RunnerFailed('lastbook-llm is busy with the index', resting=True)
        if not self.lock.acquire(timeout=self.SEARCH_S if search else -1):
            self.busy_until = time.monotonic() + self.SEARCH_S   # the other searches of this question do not wait again
            raise RunnerFailed('lastbook-llm is busy with the index', resting=True)
        try:
            if self.closed:
                raise RunnerFailed('Lastbook is closing', resting=True)
            if not force and self.proc is None and time.monotonic() < self.retry_at:
                raise RunnerFailed('lastbook-llm failed a moment ago; it is tried again later', resting=True)
            self.next_id += 1
            rid = self.next_id
            line = (json.dumps({'op': 'embed', 'id': rid, 'texts': texts, 'max_tokens': MAX_TOKENS}) + '\n').encode()
            seconds = self.SEARCH_S if search else self.BASE_S + self.PER_TEXT_S * len(texts)
            for attempt in range(2):
                started = self.proc is None or self.proc.poll() is not None
                try:
                    if started:
                        self._stop()
                        self._start()
                    v = self._ask(line, rid, len(texts), seconds)
                    self.failures, self.retry_at = 0, 0.0
                    return v
                except TextRejected:
                    self.failures, self.retry_at = 0, 0.0   # it answered: it works
                    raise
                except Exception as e:
                    self._stop()
                    if self.closed:
                        raise RunnerFailed('Lastbook is closing', resting=True) from e
                    if attempt == 0 and not started and not search and getattr(e, 'died', False):   # it died under this request
                        continue
                    if not force:
                        self.failures += 1
                        self.retry_at = time.monotonic() + min(self.RETRY_S[1], self.RETRY_S[0] * 2 ** (self.failures - 1))
                    if isinstance(e, RunnerFailed):
                        raise
                    raise RunnerFailed(f'lastbook-llm: {type(e).__name__}: {e}') from e
        finally:
            if self.closed:   # Lastbook closed during this request: nothing may stay running
                self._stop()
            self.lock.release()

    def close(self):
        """Lastbook is closing: no new requests, and the program goes. If Lastbook dies instead, the closed pipe ends it."""
        self.closed = True
        if self.lock.acquire(timeout=0):
            try:
                self._stop()
            finally:
                self.lock.release()
            return
        proc = self.proc   # a request is under way: killing the program ends it, and the request tidies up
        if proc:
            try:
                proc.kill()
            except OSError:
                pass


def made_by(model):
    """What an index records about the vectors it holds: the model, the settings that change its vectors, and the prefixes
    put before passages (none for bge) and questions. The record is compared as text: changing what goes into it turns
    every index made before the change off, so a later version that adds a setting must also add it, with the value older
    indexes used, to their stored records."""
    return {'model': model, 'dim': DIM, 'pooling': 'cls', 'passage_prefix': '', 'query_prefix': QUERY_PREFIX, 'max_tokens': MAX_TOKENS}


MODEL_SHA = {}   # (path, size, mtime_ns) -> SHA-256: the checks before each write then only look at the file's size and time


class ModelChanged(Exception):
    """The model file or the index's record is no longer what this start checked."""
    note = ('the search model file or the search index changed while Lastbook was open. Close and reopen Lastbook to check '
            'again')


def model_in_use():
    """made_by() for the model file the engine uses, named by its SHA-256 (read once while its size and time stay the same)."""
    path = GGUF if ENGINE == 'llama' else MODEL / 'model.onnx'
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in MODEL_SHA:
        with open(path, 'rb') as f:
            MODEL_SHA[key] = hashlib.file_digest(f, 'sha256').hexdigest()
    sha = MODEL_SHA[key]
    return made_by(KNOWN_MODELS.get(sha, 'sha256:' + sha))


def norm_ws(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def readable(text):
    """Skip table/spreadsheet debris and non-English runs that match every query by accident.

    Words in capitals count too: manuals print their warnings that way ("DO NOT DRINK FLOOD WATER"). A curly
    apostrophe (don’t) keeps a word whole, the same as a straight one."""
    words = re.findall(r"[A-Za-z][A-Za-z'’]+", text)
    if len(words) < 12:
        return False
    letters = sum(len(w) for w in words)
    common = sum(1 for w in words if w.lower() in COMMON)
    return letters / max(1, len(text)) > 0.55 and common / len(words) > 0.18


COMMON = set('the a an of to and in is are be for on with as by or that this it from at not can if your you use when should may will water have has which all but more they their each must after before into out other than any one two do does'.split())


def scores(mat, qv, block=4096):
    """mat (float16 rows) times qv, in float32. numpy has no fast float16 product; turning a block of rows into float32
    at a time is over ten times faster than mat @ qv and adds only one block of memory."""
    qv = np.asarray(qv, dtype=np.float32)
    out = np.empty(len(mat), dtype=np.float32)
    for i in range(0, len(mat), block):
        out[i:i + block] = mat[i:i + block].astype(np.float32) @ qv
    return out


def chunks_of(text):
    text = norm_ws(text)
    if len(text) < MINLEN:
        return []
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + CHUNK)
        if j < len(text):  # end at a sentence or word boundary
            k = text.rfind('. ', i + CHUNK // 2, j)
            j = k + 1 if k > 0 else (text.rfind(' ', i + CHUNK // 2, j) if text.rfind(' ', i + CHUNK // 2, j) > 0 else j)
        out.append(text[i:j].strip())
        if j >= len(text):
            break
        i = max(j - OVERLAP, i + 1)
    return [c for c in out if len(c) >= MINLEN and readable(c)]


def vtt_windows(path, span=45):
    """Timed transcript windows (~45 s) so answers can cite a moment in a video."""
    cues = []
    for start, lines in caption_blocks(path.read_bytes()):
        cur = [start, '']
        for line in lines:
            t = html.unescape(re.sub(r'<[^>]+>', '', line)).strip()
            if t and not cur[1].endswith(t):
                cur[1] = (cur[1] + ' ' + t).strip()
        cues.append(cur)
    out, start, buf, last = [], None, [], ''
    for t, txt in cues:
        if last and txt.startswith(last) and not txt[len(last):len(last) + 1].strip():  # a repeat ends at a word: "So" is not the start of "Some people"
            txt = txt[len(last):].strip()
        last = txt or last
        if not txt:
            continue
        if start is None:
            start = t
        buf.append(txt)
        if t - start >= span:
            out.append((start, ' '.join(buf)))
            start, buf = None, []
    if buf:
        out.append((start or 0, ' '.join(buf)))
    return [(t, norm_ws(x)) for t, x in out if len(x) > 40]


class Index:
    def __init__(self, catalog_fn, trust_fn, fts_db):
        self.catalog_fn, self.trust_fn, self.fts_db = catalog_fn, trust_fn, fts_db
        IDX.mkdir(parents=True, exist_ok=True)
        self.db_path = IDX / 'semantic.sqlite'
        self.vec_path = IDX / 'vectors.f16'
        self._tls = threading.local()
        self._excl = {'mtime': None, 'ids': set()}
        db = self._db()
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''CREATE TABLE IF NOT EXISTS chunk(id INTEGER PRIMARY KEY, doc_id TEXT, page INTEGER, t REAL, text TEXT, active INTEGER DEFAULT 1);
          CREATE INDEX IF NOT EXISTS chunk_doc ON chunk(doc_id);
          CREATE TABLE IF NOT EXISTS docstate(doc_id TEXT PRIMARY KEY, sig TEXT, nchunks INTEGER, at REAL);
          CREATE TABLE IF NOT EXISTS gaps(doc_id TEXT PRIMARY KEY, reason TEXT);''')
        db.close()
        self.lock = threading.RLock()
        self.emb = (RunnerEmbedder() if ENGINE == 'llama' else Embedder()) if AVAILABLE else None
        self.mat = None
        self.active = None
        self.status = {'state': 'starting' if AVAILABLE else 'off', 'chunks': 0, 'docs': 0, 'pending': None, 'rate': None}
        if not AVAILABLE:
            self.status['note'] = 'Meaning-based search is off: no model in this library. Keyword search still works.'
        else:
            try:
                self._check_made_by()
            except sqlite3.Error as e:   # a read-only or full drive, a write lock held over 60 s, a damaged file
                print(f'semantic index: {e}', file=sys.stderr, flush=True)
                self._off('Lastbook could not open or write to the search index: the drive may be full or read-only, or '
                          'another Lastbook may be using it. Close and reopen Lastbook to try again')
        self._load()

    def _check_made_by(self):
        """The index must have been made by the model and settings in use, or meaning search stays off: two models' vectors
        must never be mixed or compared. Nothing is deleted. An index with no passage yet takes the model in use. An index from
        before this record is adopted when a few of its passages, embedded again now, give back their stored vectors; if that
        cannot be checked, the next start tries again."""
        try:
            want = json.dumps(model_in_use(), sort_keys=True)
        except OSError as e:
            print(f'semantic index: {e}', file=sys.stderr, flush=True)
            return self._off('Lastbook could not read the search model file')
        self.made = want
        other = ('the search index in this data folder was made with another search model, or with other settings. If you '
                 'replaced the search model file, putting the earlier one back turns it on again. To build the index again for '
                 'the model now in use, close Lastbook and delete the derived/index folder in the Lastbook data folder; Lastbook '
                 'then builds it again, which can take hours')
        db = self._db()
        try:
            db.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
            row = one(db, "SELECT v FROM meta WHERE k='made_by'")
            if row and row[0] == want:
                return

            def take_if_empty(db):   # one transaction: a pass that writes its first vectors meanwhile comes before or after it
                ids = self._with_vectors(db)
                if not ids:          # nothing to mix with
                    db.execute("INSERT OR REPLACE INTO meta VALUES ('made_by', ?)", (want,))
                return ids
            ids = self._with_vectors(db) or self.tx(db, take_if_empty)   # found vectors can only lead to off or the check below
            if not ids:
                return
            if row:
                print(f'semantic index: the index records {row[0]}; in use: {want}', file=sys.stderr, flush=True)
                return self._off(other)
            same = self._same_vectors(db, ids)
            if same is None:
                return self._off('Lastbook could not check the search index against the search model this time. Close and '
                                 'reopen Lastbook to try again')
            if not same:
                return self._off(other)
            self.tx(db, lambda db: db.execute("INSERT OR IGNORE INTO meta VALUES ('made_by', ?)", (want,)))
            if one(db, "SELECT v FROM meta WHERE k='made_by'")[0] != want:     # another process recorded another model meanwhile
                return self._off(other)
        finally:
            db.close()

    def _with_vectors(self, db):
        """Passages in use that have a whole row in the vector file (an interrupted run can leave part of a row at its end)."""
        whole = self.vec_path.stat().st_size // (DIM * 2) if self.vec_path.exists() else 0
        return [i for (i,) in db.execute("SELECT id FROM chunk WHERE active=1 AND text!='' AND id<=? ORDER BY id", (whole,))]

    def _same_vectors(self, db, ids):
        """For an index with no record: do three of its passages, embedded again, give back their stored vectors? None if the
        model could not embed them."""
        pick = sorted({ids[0], ids[len(ids) // 2], ids[-1]})
        try:
            new = self.emb.embed([one(db, 'SELECT text FROM chunk WHERE id=?', (i,))[0] for i in pick])
        except WrongModel:
            return False
        except Exception as e:
            print(f'semantic index: could not check what made this index: {e}', file=sys.stderr, flush=True)
            return None
        if new.shape != (len(pick), DIM):      # a model with another vector size
            return False
        if not (np.isfinite(new).all() and np.linalg.norm(new, axis=1).all()):   # a broken answer says nothing about the index
            return None
        old = np.stack([np.fromfile(self.vec_path, dtype=np.float16, count=DIM, offset=(i - 1) * DIM * 2) for i in pick]).astype(np.float32)
        cos = (old * new).sum(1) / (np.linalg.norm(old, axis=1) * np.linalg.norm(new, axis=1) + 1e-9)
        return bool((cos >= 0.99).all())

    def _off(self, why):
        if hasattr(self.emb, 'close'):
            self.emb.close()
        self.emb = None
        self.status.update(state='off', chunks=0, docs=0, pending=None,   # the pages read chunks to say meaning search is in use
                           note=f'Meaning-based search is off: {why}. Keyword search still works.')
        print(f'semantic index: off: {why}', file=sys.stderr, flush=True)

    def _still_made_by(self, db):
        """Raises ModelChanged unless the model file and the record are still those this start checked. Called before each
        pass, each document written, and each load of another process's vectors: lastbook-llm reads the model file again at
        each of its starts, and another process may have recorded another model since this start."""
        try:
            same = (json.dumps(model_in_use(), sort_keys=True) == self.made
                    and one(db, "SELECT v FROM meta WHERE k='made_by'") == (self.made,))
        except OSError:
            same = False
        if not same:
            raise ModelChanged

    def _db(self):
        """Writer connection: autocommit, so no transaction is ever left open by accident; writes use tx()."""
        db = sqlite3.connect(self.db_path, timeout=60, isolation_level=None, check_same_thread=False)
        db.execute('PRAGMA busy_timeout=60000')
        return db

    def _ro(self):
        """Per-thread read-only connection, reused (it can never take the write lock)."""
        c = getattr(self._tls, 'ro', None)
        if c is None:
            c = sqlite3.connect(ro_uri(self.db_path), uri=True, timeout=30, isolation_level=None, check_same_thread=False)
            self._tls.ro = c
        return c

    @staticmethod
    def tx(db, fn):
        """Run fn(db) inside BEGIN IMMEDIATE … COMMIT; always roll back on error."""
        db.execute('BEGIN IMMEDIATE')
        try:
            out = fn(db)
            db.execute('COMMIT')
            return out
        except BaseException:
            db.execute('ROLLBACK')
            raise

    def refresh(self):
        """Pick up passages another process (the indexer) appended since we last loaded."""
        try:
            size = self.vec_path.stat().st_size
        except FileNotFoundError:
            return
        if self.mat is not None and size != len(self.mat) * DIM * 2:
            self._load(truncate=False)

    def _load(self, truncate=True, db=None):
        if not self.emb or not self.vec_path.exists():   # no model, or not this index's: its vectors are left as they are
            self.mat = np.zeros((0, DIM), dtype=np.float16) if AVAILABLE else None
            self.active = np.zeros(0, dtype=bool) if AVAILABLE else None
            return
        raw = np.fromfile(self.vec_path, dtype=np.float16)
        n = len(raw) // DIM
        db = db or self._ro()
        rows = one(db, 'SELECT max(id) FROM chunk')[0] or 0
        n = min(n, rows)  # vectors beyond the committed chunk rows were from an interrupted run
        self.mat = raw[:n * DIM].reshape(n, DIM)
        act = np.zeros(n, dtype=bool)
        for (i,) in db.execute('SELECT id FROM chunk WHERE active=1 AND id<=?', (n,)).fetchall():
            act[i - 1] = True
        self.active = act
        if truncate and n * DIM * 2 != self.vec_path.stat().st_size:
            with open(self.vec_path, 'r+b') as f:
                f.truncate(n * DIM * 2)
        self.status.update(chunks=int(act.sum()), docs=one(db, 'SELECT count(*) FROM docstate WHERE nchunks>0')[0])
        if self.status.get('state') == 'starting':
            self.status['state'] = 'loaded'

    # ------------------------------------------------------------ indexing --
    def excluded(self):
        """Video ids the library owner rejected (library-data/video-exclusions.json); never indexed or returned."""
        p = LIB / 'video-exclusions.json'
        try:
            m = p.stat().st_mtime
        except FileNotFoundError:
            return set()
        if m != self._excl['mtime']:
            try:
                ids = set(json.loads(p.read_text(encoding='utf-8')).get('videos', {}))
                self._excl.update(mtime=m, ids=ids | {'metadata-' + i for i in ids} | {i.replace('video-', 'transcript-', 1) for i in ids})
            except (ValueError, OSError):
                pass  # half-written file: keep the previous list
        return self._excl['ids']

    def sources(self):
        """(doc_id, signature, priority, loader) for every text the assistant may read."""
        cat = self.catalog_fn()
        excl = self.excluded()
        out = []
        for r in cat['by_id'].values():
            if r['id'] in excl:
                continue
            k = r['kind']
            if k in ('pdf', 'html', 'pptx'):
                sig = f"{r.get('sha256')}:{r.get('pages')}"
                out.append((r['id'], sig, -self.trust_fn(r)[1], ('pages', r)))
            elif k == 'video':
                tx = cat['video_tx'].get(r['path'])
                vtts = ([tx['vtt_path']] if tx and tx.get('vtt_path') else []) + [c for c in r.get('captions', []) if c.endswith('.vtt')]
                vtt = next((v for v in vtts if (LIB / v).is_file()), None)
                if vtt:
                    out.append((r['id'], 'vtt:' + vtt, -self.trust_fn(r)[1], ('vtt', vtt)))
                elif tx and (LIB / tx['path']).is_file():
                    out.append((r['id'], 'tx:' + tx['sha256'], -self.trust_fn(r)[1], ('tx', tx)))
        out.sort(key=lambda x: x[2])
        return out

    def _texts(self, doc_id, how):
        kind, ref = how
        if kind == 'pages':
            con = sqlite3.connect(ro_uri(self.fts_db), uri=True)
            rows = con.execute('SELECT page, body FROM pages WHERE doc_id=? ORDER BY CAST(page AS INTEGER)', (doc_id,)).fetchall()
            con.close()
            if not rows:  # not in the keyword index (yet); fall back to the extracted text file
                p = LIB / (ref.get('text_path') or f'text/{doc_id}.txt')
                if p.is_file():
                    t = p.read_text(encoding='utf-8', errors='replace')
                    rows = list(enumerate(t.split('\n\f\n') if '\n\f\n' in t else t.split('\f'), 1))
            return [(int(p), None, c) for p, b in rows for c in chunks_of(b)]
        if kind == 'vtt':
            return [(None, t, txt) for t, txt in vtt_windows(LIB / ref)]
        return [(None, None, c) for c in chunks_of((LIB / ref['path']).read_text(encoding='utf-8', errors='replace'))]

    def update(self, budget_s=None, batch=48):
        """Embed new/changed documents. Returns number of documents processed."""
        if not self.emb:
            self.status['state'] = 'off'
            return 0
        lockf = open(IDX / 'indexer.lock', 'w')
        try:
            lastbook_paths.try_lock(lockf)
        except OSError:  # another process is indexing; follow its progress if it writes what this start checked
            lockf.close()
            try:
                self._still_made_by(self._ro())
            except ModelChanged:
                self._off(ModelChanged.note)
                return 0
            self.refresh()
            self.status['state'] = 'indexing (other process)'
            return -1
        try:
            db = self._db()
            try:
                self._still_made_by(db)
                self._reconcile(db)
                self._load(truncate=True, db=db)
            finally:
                db.close()
            return self._update(budget_s, batch)
        except ModelChanged:
            self._off(ModelChanged.note)
            return 0
        finally:
            lastbook_paths.unlock(lockf)
            lockf.close()

    def _reconcile(self, db):
        """Vectors and passage rows must line up 1:1. If an earlier run left rows without vectors, drop those rows
        and mark their documents for re-embedding instead of refusing to index."""
        vec_rows = self.vec_path.stat().st_size // (DIM * 2) if self.vec_path.exists() else 0
        rows = one(db, 'SELECT max(id) FROM chunk')[0] or 0
        if rows <= vec_rows:
            return 0
        docs = [d for (d,) in db.execute('SELECT DISTINCT doc_id FROM chunk WHERE id>?', (vec_rows,)).fetchall()]

        def w(db):
            db.execute('DELETE FROM chunk WHERE id>?', (vec_rows,))
            for d in docs:
                db.execute('UPDATE chunk SET active=0 WHERE doc_id=?', (d,))
                db.execute('DELETE FROM docstate WHERE doc_id=?', (d,))
        self.tx(db, w)
        self.status['repaired'] = {'rows_without_vectors': rows - vec_rows, 'documents_requeued': docs[:20],
                                   'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
        return rows - vec_rows

    def _update(self, budget_s, batch):
        db = self._db()
        try:
            return self._update_with(db, budget_s, batch)
        finally:
            db.close()

    def _hide(self, db, doc_ids, forget_text=False):
        """Deactivate every passage of these documents (removed, rejected or replaced)."""
        ids = [i for d in doc_ids for (i,) in db.execute('SELECT id FROM chunk WHERE doc_id=? AND active=1', (d,)).fetchall()]

        def w(db):
            for d in doc_ids:
                db.execute("UPDATE chunk SET active=0" + (", text=''" if forget_text else '') + " WHERE doc_id=?", (d,))
                db.execute('DELETE FROM docstate WHERE doc_id=?', (d,))
                if forget_text:
                    db.execute('DELETE FROM gaps WHERE doc_id=?', (d,))
        self.tx(db, w)
        with self.lock:
            for i in ids:
                if i <= len(self.active):
                    self.active[i - 1] = False
        return len(ids)

    def _update_with(self, db, budget_s, batch):
        known = dict(db.execute('SELECT doc_id, sig FROM docstate').fetchall())
        srcs = self.sources()
        excl = self.excluded()
        todo = [s for s in srcs if known.get(s[0]) != s[1]]
        live = {s[0] for s in srcs}
        # Prune: documents gone from the catalog, and rejected videos (also any stray passages they left behind).
        stale = [d for d in known if d not in live]
        stray = [d for (d,) in db.execute(f"SELECT DISTINCT doc_id FROM chunk WHERE active=1 AND doc_id IN ({','.join('?' * len(excl))})", list(excl)).fetchall()] if excl else []
        pruned = 0
        if stale or stray:
            rejected = [d for d in set(stale) | set(stray) if d in excl]
            pruned += self._hide(db, [d for d in stale if d not in excl])
            pruned += self._hide(db, rejected, forget_text=True)
        self.status.update(state='indexing' if todo else 'up to date', pending=len(todo), pruned_last=pruned)
        t0, done, nchunks, passed_over = time.time(), 0, 0, 0
        for doc_id, sig, _, how in todo:
            if budget_s and time.time() - t0 > budget_s:
                break
            gap = None
            try:
                parts = self._texts(doc_id, how)
            except Exception as e:
                parts, gap = [], f'unreadable: {e}'[:200]
            if not parts and not gap:
                gap = 'no extractable text'
            def embed_all(force=False):
                return [self.emb.embed([p[2] for p in parts[i:i + batch]], force=force) for i in range(0, len(parts), batch)]
            try:
                vecs = embed_all()
            except (TextRejected, RunnerFailed) as e:
                vecs = self._embed_again(doc_id, e, embed_all)   # raises when the program is the trouble: the pass ends
                if vecs is None:   # passed over for this pass only: nothing is written, so the next pass tries it again
                    passed_over += 1
                    if passed_over >= self.PASS_OVER_LIMIT:
                        raise RunnerFailed(f'{passed_over} documents in a row could not be embedded; the program is likely '
                                           'the trouble, so this pass ends here')
                    continue
            passed_over = 0
            v = np.concatenate(vecs).astype(np.float16) if parts else None
            with self.lock:
                old = [i for (i,) in db.execute('SELECT id FROM chunk WHERE doc_id=? AND active=1', (doc_id,)).fetchall()]
                start = (one(db, 'SELECT max(id) FROM chunk')[0] or 0) + 1
                if start - 1 != len(self.mat):  # vectors and rows drifted (e.g. an interrupted run): realign, don't fail
                    self._reconcile(db)
                    self._load(truncate=True, db=db)
                    start = (one(db, 'SELECT max(id) FROM chunk')[0] or 0) + 1
                    if start - 1 != len(self.mat):
                        raise RuntimeError(f'vector file has {len(self.mat)} rows but the database has {start - 1}; rebuild derived/index')

                def w(db):
                    self._still_made_by(db)   # in the write transaction: no other process can record another model until it ends
                    db.execute('UPDATE chunk SET active=0 WHERE doc_id=?', (doc_id,))
                    if parts:
                        db.executemany('INSERT INTO chunk(id,doc_id,page,t,text,active) VALUES (?,?,?,?,?,1)',
                                       [(start + j, doc_id, p[0], p[1], p[2]) for j, p in enumerate(parts)])
                    if gap:
                        db.execute('INSERT OR REPLACE INTO gaps VALUES (?,?)', (doc_id, gap))
                    else:
                        db.execute('DELETE FROM gaps WHERE doc_id=?', (doc_id,))
                    db.execute('INSERT OR REPLACE INTO docstate VALUES (?,?,?,?)', (doc_id, sig, len(parts), time.time()))
                    if parts:  # append vectors last, inside the transaction: a failed write never leaves orphan rows
                        with open(self.vec_path, 'ab') as f:
                            f.write(v.tobytes())
                self.tx(db, w)
                if parts:
                    self.mat = np.concatenate([self.mat, v]) if len(self.mat) else v
                    self.active = np.concatenate([self.active, np.ones(len(v), dtype=bool)])
                for i in old:
                    self.active[i - 1] = False
            done += 1
            nchunks += len(parts)
            el = time.time() - t0
            self.status.update(pending=len(todo) - done, chunks=int(self.active.sum()),
                               rate=round(nchunks / el, 1) if el > 1 else None)
        self.status.update(state='up to date' if done == len(todo) else 'indexing',
                           docs=one(db, 'SELECT count(*) FROM docstate WHERE nchunks>0')[0])
        return done

    PASS_OVER_LIMIT = 3   # documents passed over in a row before a pass ends: by then the program, not the texts, is the trouble

    def _embed_again(self, doc_id, e, embed_all):
        """Embedding this document failed. If the program still embeds a check text, the document is tried once more, so a
        passing failure goes through. Returns its vectors, or None if it fails again: it is passed over for this pass. Nothing
        is written for it, so the next pass tries it again: a failure that was the program's (memory, sleep, a slow machine)
        never marks a document. Raises when the program cannot even embed the check text, so the pass ends."""
        if getattr(e, 'resting', False):
            raise e
        self.emb.embed(['a short text to check the program still works'], force=True)
        try:
            return embed_all(force=True)
        except (TextRejected, RunnerFailed) as again:
            if getattr(again, 'resting', False):
                raise
            print(f'semantic index: passing over {doc_id} for now: {again}', file=sys.stderr, flush=True)
            return None

    def run_forever(self, every=300):
        while True:
            try:
                n = self.update(budget_s=None)
                if n >= 0:  # a successful pass clears any earlier error
                    self.status.pop('error', None)
                    self.status['last_ok'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            except Exception as e:
                print(f'semantic index: {e}', file=sys.stderr, flush=True)
                self.status.update(state='error', error=type(e).__name__, error_at=time.strftime('%Y-%m-%dT%H:%M:%S'))  # shown to clients: no paths
            time.sleep(every)


    # ------------------------------------------------------------- search --
    def semantic(self, q, k=60, allowed=None, floor=0.55):
        emb = self.emb   # read once: indexing may turn meaning search off meanwhile
        if not emb or self.mat is None or not len(self.mat):
            return []
        try:
            qv = emb.embed([QUERY_PREFIX + q], search=True)[0]   # float32: scores() multiplies in float32 (#224)
        except Exception as e:   # meaning search is an extra: when it fails, keyword search and Chat carry on without it
            if 'search_error' not in self.status:   # the first of a run of failures; in full if it is not the program's
                print(f'semantic search failed; keyword search carries on: {e}', file=sys.stderr, flush=True)
                if not isinstance(e, (RunnerFailed, TextRejected)):
                    traceback.print_exc()
            self.status['search_error'] = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'kind': type(e).__name__}   # shown to clients: no paths
            return []
        self.status.pop('search_error', None)
        with self.lock:
            m, act = self.mat, self.active
            s = scores(m, qv)
            s[~act[:len(s)]] = -1
        top = np.nonzero(s >= floor)[0]  # everything above the floor, best first: filtering by allowed happens before any cut
        top = top[np.argsort(-s[top])]
        db = self._ro()
        excl = self.excluded()
        out, seen = [], {}
        for b in range(0, len(top), 500):  # doc ids in batches, text only for what survives the filters
            ids = [int(i) + 1 for i in top[b:b + 500]]
            docs = dict(db.execute(f"SELECT id,doc_id FROM chunk WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall())
            for i in top[b:b + 500]:
                d = docs.get(int(i) + 1)
                if d is None or d in excl:
                    continue
                if d not in seen:
                    seen[d] = not allowed or bool(allowed(d))
                if not seen[d]:
                    continue
                row = one(db, 'SELECT doc_id,page,t,text FROM chunk WHERE id=?', (int(i) + 1,))
                if not row or not readable(row[3]):  # indexed before the quality filter existed
                    continue
                out.append({'doc_id': row[0], 'page': row[1], 't': row[2], 'text': row[3], 'sem': float(s[i])})
                if len(out) >= k:
                    return out
        return out

    def gaps_for(self, doc_ids):
        db = self._ro()
        return dict(db.execute(f"SELECT doc_id, reason FROM gaps WHERE doc_id IN ({','.join('?' * len(doc_ids))})", list(doc_ids)).fetchall()) if doc_ids else {}


def one(db, sql, args=()):
    """First row of a query, always stepping the statement to completion (an unfinished statement keeps an old
    snapshot of the database open in WAL mode, which is how stale row counts crept in before)."""
    rows = db.execute(sql, args).fetchall()
    return rows[0] if rows else None


def rrf(lists, k=60):
    scores = {}
    for name, items in lists:
        items = list(dict.fromkeys(items))  # a page split into several passages counts once, at its best rank
        for rank, key in enumerate(items):
            e = scores.setdefault(key, {'score': 0.0, 'ranks': {}})
            e['score'] += 1 / (k + rank + 1)
            e['ranks'][name] = rank + 1
    return scores


if __name__ == '__main__':  # python retrieval.py  -> build/refresh the semantic index once
    sys.path.insert(0, str(lastbook_paths.APP))
    import server
    ix = Index(server.catalog, server.trust, server.library.DB)
    print('pending documents:', len([1 for s in ix.sources()]), flush=True)
    stop = threading.Event()
    def report():
        while not stop.wait(30):
            print(json.dumps(ix.status), flush=True)
    threading.Thread(target=report, daemon=True).start()
    n = ix.update()
    stop.set()
    print('done', n, json.dumps(ix.status), flush=True)
