"""Part 2 (#403) with other section cutoffs: run the branch's own score.py with engine.sections.LONG / SECTION changed.

    python -B run_cut.py <checkout> <LONG> <SECTION> <score.py args...>

Nothing in the checkout is edited: the module's constants and cut()'s default size are set in this process before
score.py runs. The sections file's signature contains LONG and SECTION, so each pair gets its own file; give each pair
its own --sections folder (ensure() removes older files in the folder it writes to).
"""
import runpy
import sys
from pathlib import Path

code, long_, sec = Path(sys.argv[1]).resolve(), int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, str(code))
from engine import sections  # noqa: E402  (the same module object score.py imports later)

sections.LONG, sections.SECTION = long_, sec
sections.cut.__defaults__ = (sec,)
print(f'sections: LONG={sections.LONG} SECTION={sections.SECTION}', flush=True)
sys.argv = [str(code / 'tools' / 'search_eval' / 'score.py')] + sys.argv[4:] + ['--code', str(code)]
runpy.run_path(sys.argv[0], run_name='__main__')
