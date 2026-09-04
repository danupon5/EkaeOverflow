#!/usr/bin/env python3
"""Run the sync core against a real .eml, not a hand-written fixture.

Pass the path to an .eml file; its text/plain and text/html parts are
pulled out and embedded in a browser test page, which then replays the
kind of edit a user actually makes and checks where it landed.

Run: python3 tests/build-real-message-test.py /path/to/message.eml
     then open tests/real-message-tests.html
"""
import email
import json
import os
import re
import sys
from email import policy

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, os.pardir, 'index.html')
OUT = os.path.join(HERE, 'real-message-tests.html')

if len(sys.argv) < 2:
    sys.exit('usage: build-real-message-test.py <message.eml>')

msg = email.message_from_binary_file(open(sys.argv[1], 'rb'), policy=policy.default)
text = html = None
for part in msg.walk():
    if 'attachment' in str(part.get('Content-Disposition') or ''):
        continue
    if part.get_content_type() == 'text/plain' and text is None:
        text = part.get_content()
    if part.get_content_type() == 'text/html' and html is None:
        html = part.get_content()
if not text or not html:
    sys.exit('message needs both a text/plain and a text/html part')

src = open(SRC, encoding='utf-8').read()
m = re.search(r'// ==== SYNC-CORE-START ====(.*?)// ==== SYNC-CORE-END ====', src, re.S)
if not m:
    sys.exit('SYNC-CORE markers not found in index.html')
core = m.group(1)

fixture = json.dumps({'text': text, 'html': html}, ensure_ascii=False)

tests = r'''
const results = [];
const notes = [];
function check(name, cond, detail) {
  results.push({ name: name, pass: !!cond, detail: cond ? '' : String(detail || '').slice(0, 400) });
}

const TEXT = FIXTURE.text;
const HTML = FIXTURE.html;

// What the HTML looks like after a plain round-trip through the DOM, so
// "nothing else changed" can be asserted against re-serialization rather
// than against the original source formatting.
function roundTrip(html) {
  const d = document.createElement('div');
  d.innerHTML = html;
  return d.innerHTML;
}
const BASELINE = roundTrip(HTML);

function run(newText) {
  state.html = HTML;
  state.originalText = TEXT;
  state.text = newText;
  const changed = syncTextEditIntoHtml();
  return { changed: changed, html: state.html };
}
const at = (h, s) => h.indexOf(s);

const PARA_END = 'ในการ scan ให้เราได้ครับ';   // last line of the live body
const SIG = 'Mr. Anusorn Sirichan';           // signature, just below it
const QUOTE = 'Forwarded message';            // quoted thread further down

notes.push('plain text: ' + TEXT.length + ' chars, ' + TEXT.split('\n').length + ' lines');
notes.push('html: ' + HTML.length + ' chars, &nbsp; entities: ' + (HTML.match(/&nbsp;/g) || []).length);
notes.push('body paragraph found in text: ' + (TEXT.indexOf(PARA_END) !== -1));

// 1. The exact edit that was going wrong: one line typed after the body
//    paragraph, with a blank line under it.
(function () {
  const t = TEXT.replace('Best Regards,', 'test12312312121\n\nBest Regards,');
  const r = run(t);
  const n = (r.html.match(/test12312312121/g) || []).length;
  check('1a applied', r.changed && n === 1, 'occurrences=' + n);
  check('1b own div', at(r.html, '<div>test12312312121</div>') !== -1, r.html.slice(0, 300));
  check('1c after the body paragraph', at(r.html, 'test12312312121') > at(r.html, PARA_END),
        'ins=' + at(r.html, 'test12312312121') + ' para=' + at(r.html, PARA_END));
  check('1d above the signature', at(r.html, 'test12312312121') < at(r.html, SIG),
        'ins=' + at(r.html, 'test12312312121') + ' sig=' + at(r.html, SIG));
  check('1e not in the quoted thread', at(r.html, 'test12312312121') < at(r.html, QUOTE),
        'ins=' + at(r.html, 'test12312312121') + ' quote=' + at(r.html, QUOTE));
  // Nothing but the insert changed anywhere else in the message.
  const stripped = r.html.replace('<div>test12312312121</div><div><br></div>', '');
  check('1f rest of the message untouched', stripped === BASELINE,
        'len ' + stripped.length + ' vs baseline ' + BASELINE.length);
  const idx = at(r.html, 'test12312312121');
  notes.push('context: ...' + r.html.slice(Math.max(0, idx - 160), idx + 90).replace(/\s+/g, ' ') + '...');
})();

// 2. Two typed lines with a blank line between them keep the gap.
(function () {
  const t = TEXT.replace('Best Regards,', 'LINE_A\n\nLINE_B\n\nBest Regards,');
  const r = run(t);
  check('2a blank line preserved between them',
        at(r.html, '<div>LINE_A</div><div><br></div><div>LINE_B</div>') !== -1,
        r.html.slice(Math.max(0, at(r.html, 'LINE_A') - 80), at(r.html, 'LINE_A') + 200));
})();

// 3. Editing an existing line replaces it rather than duplicating it —
//    and touches only the signature, not the copy of the same number
//    sitting in the quoted thread below in a different format.
(function () {
  const t = TEXT.replace('Mobile : 089-822-2191', 'Mobile : 081-111-2222');
  const r = run(t);
  check('3a new value present once', (r.html.match(/081-111-2222/g) || []).length === 1,
        'occurrences=' + (r.html.match(/081-111-2222/g) || []).length);
  check('3b old signature line replaced', (r.html.match(/Mobile : 089-822-2191/g) || []).length === 0,
        'left=' + (r.html.match(/Mobile : 089-822-2191/g) || []).length);
  check('3c quoted copy deliberately left alone',
        (r.html.match(/211300396 \/ 089-822-2191/g) || []).length === 1,
        'quoted copies=' + (r.html.match(/211300396 \/ 089-822-2191/g) || []).length);
})();

// 4. Pressing the button again with nothing newly typed changes nothing.
(function () {
  const t = TEXT.replace('Best Regards,', 'ONLYONCE\n\nBest Regards,');
  run(t);
  const afterFirst = state.html;
  state.text = t;
  const again = syncTextEditIntoHtml();
  check('4a no-op on repeat', again === false, 'returned ' + again);
  check('4b unchanged html', state.html === afterFirst, 'html differs');
  check('4c still exactly one copy', (state.html.match(/ONLYONCE/g) || []).length === 1,
        'occurrences=' + (state.html.match(/ONLYONCE/g) || []).length);
})();

// 5. A Thai line typed into the body survives intact.
(function () {
  const thai = 'รบกวนช่วยตรวจสอบด้วยครับ ขอบคุณครับ';
  const t = TEXT.replace('Best Regards,', thai + '\n\nBest Regards,');
  const r = run(t);
  check('5a thai text intact', at(r.html, thai) !== -1, r.html.slice(0, 200));
  check('5b placed in the live body', at(r.html, thai) < at(r.html, QUOTE) && at(r.html, thai) > at(r.html, PARA_END),
        'ins=' + at(r.html, thai));
})();

const failed = results.filter(r => !r.pass);
document.getElementById('out').textContent =
  'PASS ' + (results.length - failed.length) + '/' + results.length + '\n\n'
  + results.map(r => (r.pass ? 'ok   ' : 'FAIL ') + r.name + (r.pass ? '' : '\n       ' + r.detail)).join('\n')
  + '\n\n--- notes ---\n' + notes.join('\n');
window.__testSummary = { total: results.length, failed: failed.length };
'''

page = """<!doctype html>
<meta charset="utf-8">
<title>real message sync tests</title>
<style>body{font:13px ui-monospace,monospace;padding:16px;white-space:pre-wrap;word-break:break-word}</style>
<pre id="out">running...</pre>
<script>
(function () {
  const FIXTURE = __FIXTURE__;
  const state = { html: '', text: '', originalText: '' };
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
__CORE__
  try {
__TESTS__
  } catch (e) {
    document.getElementById('out').textContent = 'THREW: ' + (e && e.stack || e);
    window.__testSummary = { total: 0, failed: 1 };
  }
})();
</script>
"""

page = page.replace('__FIXTURE__', fixture).replace('__CORE__', core).replace('__TESTS__', tests)
open(OUT, 'w', encoding='utf-8').write(page)
print('wrote', OUT, len(page), 'bytes')
