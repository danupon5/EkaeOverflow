#!/usr/bin/env python3
"""Generate a browser test page for the plain-text -> HTML sync core.

Run: python3 tests/build-sync-tests.py, then open tests/sync-tests.html.

The core is extracted verbatim from index.html between the SYNC-CORE
markers, so the tests can never drift from the shipped code.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, os.pardir, 'index.html')
OUT = os.path.join(HERE, 'sync-tests.html')

src = open(SRC, encoding='utf-8').read()
m = re.search(r'// ==== SYNC-CORE-START ====(.*?)// ==== SYNC-CORE-END ====', src, re.S)
if not m:
    sys.exit('SYNC-CORE markers not found in index.html')
core = m.group(1)

tests = r'''
const results = [];
function check(name, cond, detail) {
  results.push({ name: name, pass: !!cond, detail: cond ? '' : (detail || '') });
}

// A Gmail-shaped message: &nbsp; inside the paragraph, the body soft-wrapped
// in the plain-text part but a single <div> in HTML, and a quoted copy of the
// same sentences further down (the classic wrong-place trap).
const HTML = '<div dir="ltr">'
  + '<div>'
  + '<div class="gd">Jack,</div>'
  + '<div class="gd"><br></div>'
  + '<div class="gd">Tenable Prerequisite AAA BBB CCC DDD&nbsp;EEE&nbsp;FFF GGG HHH</div>'
  + '<br clear="all">'
  + '</div>'
  + '<div><div dir="ltr" class="gmail_signature"><div dir="ltr">'
  + '<div><br></div><div>Best Regards,</div><div>Mr. Anusorn Sirichan</div>'
  + '</div></div></div>'
  + '<div class="gmail_quote">'
  + '<div>---------- Forwarded message ---------</div>'
  + '<div>Jack,</div>'
  + '<div>Tenable Prerequisite AAA BBB CCC DDD EEE FFF GGG HHH</div>'
  + '<div>Best Regards,</div>'
  + '</div>'
  + '</div>';

const TEXT = [
  'Jack,',
  '',
  'Tenable Prerequisite AAA BBB CCC',
  'DDD EEE FFF GGG HHH',
  '',
  '',
  'Best Regards,',
  'Mr. Anusorn Sirichan',
  '',
  '---------- Forwarded message ---------',
  'Jack,',
  'Tenable Prerequisite AAA BBB CCC DDD EEE FFF GGG HHH',
  'Best Regards,',
  ''
].join('\n');

function run(newText, html, oldText) {
  state.html = html === undefined ? HTML : html;
  state.originalText = oldText === undefined ? TEXT : oldText;
  state.text = newText;
  const changed = syncTextEditIntoHtml();
  return { changed: changed, html: state.html };
}
const at = (h, s) => h.indexOf(s);

// 1. Blank lines survive, and the insert lands in the live body — above the
//    signature and nowhere near the quoted copy.
(function () {
  const t = TEXT.replace('Best Regards,\nMr. Anusorn Sirichan',
                         'test12345\n\nBest Regards,\nMr. Anusorn Sirichan');
  const r = run(t);
  check('1a insert applied', r.changed && at(r.html, 'test12345') !== -1, r.html);
  check('1b wrapped in its own div', at(r.html, '<div>test12345</div>') !== -1, r.html);
  check('1c after the body paragraph', at(r.html, 'test12345') > at(r.html, 'GGG HHH'), r.html);
  check('1d before the signature', at(r.html, 'test12345') < at(r.html, 'Best Regards,'), r.html);
  check('1e not in the quoted copy', at(r.html, 'test12345') < at(r.html, 'Forwarded message'), r.html);
  check('1f body text intact', at(r.html, 'Tenable Prerequisite AAA BBB CCC DDD') !== -1, r.html);
})();

// 2. A blank line between two typed lines becomes a real blank line.
(function () {
  const t = TEXT.replace('Best Regards,\nMr.', 'A1\n\nB2\n\nBest Regards,\nMr.');
  const r = run(t);
  check('2a both lines present', at(r.html, '<div>A1</div>') !== -1 && at(r.html, '<div>B2</div>') !== -1, r.html);
  check('2b blank line kept between them',
        at(r.html, '<div>A1</div><div><br></div><div>B2</div>') !== -1, r.html);
})();

// 3. Several consecutive blank lines are all kept.
(function () {
  const t = TEXT.replace('Best Regards,\nMr.', 'X1\n\n\n\nY2\n\nBest Regards,\nMr.');
  const r = run(t);
  check('3a three blank divs between X1 and Y2',
        at(r.html, '<div>X1</div><div><br></div><div><br></div><div><br></div><div>Y2</div>') !== -1, r.html);
})();

// 4. Editing a line replaces it instead of duplicating it.
(function () {
  const t = TEXT.replace('Mr. Anusorn Sirichan', 'Mr. Anusorn S.');
  const r = run(t);
  const olds = (r.html.match(/Anusorn Sirichan/g) || []).length;
  check('4a new text present', at(r.html, 'Mr. Anusorn S.') !== -1, r.html);
  check('4b old line gone (no duplicate)', olds === 0, 'occurrences=' + olds + ' :: ' + r.html);
})();

// 5. Deleting a line removes it from the HTML.
(function () {
  const t = TEXT.replace('Best Regards,\nMr. Anusorn Sirichan', 'Best Regards,');
  const r = run(t);
  check('5a line removed', (r.html.match(/Anusorn Sirichan/g) || []).length === 0, r.html);
  check('5b neighbour kept', at(r.html, 'Best Regards,') !== -1, r.html);
})();

// 6. An edit at the very end of the message appends at the end.
(function () {
  const t = TEXT + 'TAILLINE\n';
  const r = run(t);
  check('6a appended', at(r.html, 'TAILLINE') !== -1, r.html);
  check('6b after everything else', at(r.html, 'TAILLINE') > at(r.html, 'Forwarded message'), r.html);
})();

// 7. An edit at the very start goes in before the first line.
(function () {
  const t = 'HEADLINE\n\n' + TEXT;
  const r = run(t);
  check('7a inserted', at(r.html, 'HEADLINE') !== -1, r.html);
  check('7b before the first line', at(r.html, 'HEADLINE') < at(r.html, 'Jack,'), r.html);
})();

// 8. A line typed inside a soft-wrapped paragraph rejoins that paragraph
//    instead of splitting the <div> apart.
(function () {
  const t = TEXT.replace('AAA BBB CCC\nDDD EEE FFF', 'AAA BBB CCC\nINLINEX\nDDD EEE FFF');
  const r = run(t);
  const div = (r.html.match(/<div class="gd">Tenable[^<]*<\/div>/) || [''])[0];
  check('8a inserted', at(r.html, 'INLINEX') !== -1, r.html);
  check('8b stayed inside the paragraph div', div.indexOf('INLINEX') !== -1, div || r.html);
  check('8c paragraph not fused into a word',
        /CCC INLINEX/.test(r.html) && /INLINEX DDD/.test(r.html.replace(/&nbsp;/g, ' ')), div || r.html);
})();

// 9. Syncing again with nothing newly typed is a no-op (no duplicates).
(function () {
  const t = TEXT.replace('Best Regards,\nMr.', 'ONCE\n\nBest Regards,\nMr.');
  const first = run(t);
  state.text = t; // same text, user pressed the button again
  const again = syncTextEditIntoHtml();
  const count = (state.html.match(/ONCE/g) || []).length;
  check('9a second run is a no-op', again === false, 'returned ' + again);
  check('9b inserted exactly once', count === 1, 'occurrences=' + count);
})();

// 10. The anchor still matches across &nbsp; in the HTML.
(function () {
  const t = TEXT.replace('DDD EEE FFF GGG HHH\n', 'DDD EEE FFF GGG HHH\n\nNBSPOK\n');
  const r = run(t);
  check('10a anchored past &nbsp;', at(r.html, 'NBSPOK') !== -1, r.html);
  check('10b landed in the live body, not the quote',
        at(r.html, 'NBSPOK') !== -1 && at(r.html, 'NBSPOK') < at(r.html, 'Forwarded message'), r.html);
})();

// 11. A full HTML document keeps its <html>/<body> wrapper.
(function () {
  const doc = '<html><head><meta charset="utf-8"></head><body><div>Jack,</div>'
    + '<div>Tenable Prerequisite AAA BBB CCC DDD EEE FFF GGG HHH</div>'
    + '<div>Best Regards,</div></body></html>';
  const shortText = 'Jack,\nTenable Prerequisite AAA BBB CCC DDD EEE FFF GGG HHH\nBest Regards,\n';
  const t = shortText.replace('Best Regards,', 'DOCLINE\n\nBest Regards,');
  const r = run(t, doc, shortText);
  check('11a inserted', at(r.html, 'DOCLINE') !== -1, r.html);
  check('11b body wrapper preserved', /<body[\s>]/i.test(r.html), r.html);
})();

const failed = results.filter(r => !r.pass);
document.getElementById('out').textContent =
  'PASS ' + (results.length - failed.length) + '/' + results.length + '\n\n'
  + results.map(r => (r.pass ? 'ok   ' : 'FAIL ') + r.name + (r.pass ? '' : '\n       ' + r.detail)).join('\n');
window.__testSummary = { total: results.length, failed: failed.length, failures: failed };
'''

page = """<!doctype html>
<meta charset="utf-8">
<title>sync core tests</title>
<style>body{font:13px ui-monospace,monospace;padding:16px;white-space:pre-wrap}</style>
<pre id="out">running...</pre>
<script>
(function () {
  const state = { html: '', text: '', originalText: '' };
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
__CORE__
  try {
__TESTS__
  } catch (e) {
    document.getElementById('out').textContent = 'THREW: ' + (e && e.stack || e);
    window.__testSummary = { total: 0, failed: 1, failures: [{ name: 'exception', detail: String(e) }] };
  }
})();
</script>
"""

page = page.replace('__CORE__', core).replace('__TESTS__', tests)
open(OUT, 'w', encoding='utf-8').write(page)
print('wrote', OUT, len(page), 'bytes; core', len(core), 'bytes')
