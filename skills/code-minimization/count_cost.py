#!/usr/bin/env python3
"""Implementation cost of a project's code (skill code-minimization): its code tokens, weighted by the copies to come.

cost = 1 x the tokens of the shared files + WEIGHT x the tokens of the client files (WEIGHT 2 by default: plan for twice
as many clients as today). A file copied into each client is passed once per copy, so each copy counts.
A token is a word or one symbol of code (\\w+, or any other non-space character): spacing changes nothing
(`2>/dev/null` = `2> /dev/null` = 5) and a long clear name costs the same as a short one.
Free (never cut them to save tokens): comments, docstrings, blank lines, and the text of a string (a message, a log line,
a path): a string counts 1, plus the code inside it ($x, ${…}, $(…), `…` in shell; {…} in f-strings; ${…} in JS).
A string that is itself code counts as code: in shell, one read by awk/sed/jq/perl/sh/bash/ssh/python on its line, or
one holding a newline, `;`, `|` or `$(`; a heredoc read by one of those; in HTML, an on…="…" handler;
in Python, a string holding markup (a page template): counted as HTML, its tags, CSS and JS.
Settings files (any other extension: .conf, .env, .json…) count 1 per line that is not blank or a comment.
Usage: count_cost.py [-v] [--weight W] --shared FILE… [--client FILE…]   (-v: one row per file)"""
import argparse, io, pathlib, re, tokenize

def n_words(text):
    # Tokens of plain code: each word, each symbol
    return len(re.findall(r'\w+|[^\w\s]', text))

CODE_CMD = re.compile(r'(?:^|[\s;|&(`])(awk|gawk|sed|jq|perl|sh|bash|zsh|ssh|python3?)\b[^;|&\n]*$')

def sh_tokens(text):
    n = len(text)
    def lang_at(i):   # 'py' or 'sh' when the string or heredoc starting at i is read by a code command on its line
        m = CODE_CMD.search(text[text.rfind('\n', 0, i) + 1:i])
        return m and ('py' if m.group(1).startswith('python') else 'sh')
    def string(s, lang):   # a string's tokens: its code in full, or 1 for its text
        return py_tokens(s) if lang == 'py' else sh_tokens(s) if lang else 1
    def dquote(i):   # a "…" from after its opening quote → (1 + the tokens of the code in it, index after it)
        count = 1
        while i < n and text[i] != '"':
            if text[i] == '\\': i += 2
            elif text.startswith('$((', i): k, i = code(i + 3, True); count += k + 5; i += 1   # $(( … )), arithmetic
            elif text.startswith('$(', i): k, i = code(i + 2, True); count += k + 3            # $( … )
            elif text.startswith('${', i):
                j, depth = i + 2, 1
                while j < n and depth: depth += {'{': 1, '}': -1}.get(text[j], 0); j += 1
                count += n_words(text[i:j]); i = j
            elif m := re.compile(r'\$(\w+|[@*#?$!-])').match(text, i): count += n_words(m.group()); i = m.end()
            elif text[i] == '`':
                j = text.find('`', i + 1); j = n if j < 0 else j; count += sh_tokens(text[i + 1:j]) + 2; i = j + 1
            else: i += 1
        return count, i + 1
    def code(i, stop):   # code from i to its end, or (stop) to the unmatched ')' of a $( ) → (tokens, index after)
        count, l_buf, depth, l_here = 0, [], 0, []
        while i < n:
            c = text[i]
            if c == '\\': l_buf.append(text[i:i + 2]); i += 2
            elif c == '#' and (i == 0 or text[i - 1] in ' \t\n;(|&'):          # a comment, to the end of the line
                i = text.find('\n', i); i = n if i < 0 else i
            elif c == '\n' and l_here:                                         # the bodies of this line's heredocs
                for delim, lang in l_here:
                    m = re.compile(r'^[ \t]*' + re.escape(delim) + r'$', re.M).search(text, i + 1)
                    body = text[i + 1:m.start() if m else n]
                    # a text body counts like a "…" string: 1, plus the code in it
                    count += string(body, lang) if lang else sh_tokens('"' + body.replace('"', '\\"') + '"')
                    i = m.end() if m else n
                l_here = []; l_buf.append(' ')
            elif text.startswith('<<', i) and not text.startswith('<<<', i) and \
                    (m := re.compile(r'<<-?[ \t]*([\'"]?)(\w+)\1').match(text, i)):
                l_here.append((m.group(2), lang_at(i))); l_buf.append(' << '); i = m.end()
            elif c == "'":
                j = text.find("'", i + 1); j = n if j < 0 else j; s = text[i + 1:j]
                count += string(s, lang_at(i) or (re.search(r'[\n;|]|\$\(', s) and 'sh')); l_buf.append(' '); i = j + 1
            elif c == '"':
                lang = lang_at(i); k, j = dquote(i + 1)
                count += string(text[i + 1:j - 1], lang) if lang else k; l_buf.append(' '); i = j
            elif stop and c in '()' and (depth := depth + (1 if c == '(' else -1)) < 0:
                return count + n_words(''.join(l_buf)), i + 1
            else: l_buf.append(c); i += 1
        return count + n_words(''.join(l_buf)), n
    return code(0, False)[0]

def py_tokens(text):
    try: l_tok = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type not in (tokenize.COMMENT, tokenize.NL)]
    except (tokenize.TokenError, SyntaxError): return sh_tokens(text)   # not Python (a python -c fragment): read as shell
    l_struct = (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)
    count = 0
    for k, t in enumerate(l_tok):
        if t.type in l_struct: continue
        if t.type != tokenize.STRING: count += n_words(t.string); continue
        # A string alone on its line is a docstring: free. An f-string: 1, plus the code in its {…}.
        # A string holding markup (a tag) is code: counted as HTML, each {…} as a placeholder text, plus its code
        if (k == 0 or l_tok[k - 1].type in l_struct) and l_tok[k + 1].type in l_struct: continue
        prefix = re.match(r'[A-Za-z]*', t.string).group().lower()
        body = t.string[len(prefix):].strip('"\'')
        text, l_expr = fstring_parts(body) if 'f' in prefix else (body, [])
        # each {…} is Python: a quoted message in it counts 1 too (in parentheses, so a lone string is not taken for a docstring)
        count += (html_tokens(text) if re.search(r'<[A-Za-z!/]', text) else 1) + sum(py_tokens(f'({x})') - 2 for x in l_expr)
    return count

def fstring_parts(body):
    # An f-string's body → (its text, each {…} replaced by a word and {{ }} by { }, [the code of each {…}])
    l_text, l_expr, i, n = [], [], 0, len(body)
    while i < n:
        if body.startswith(('{{', '}}'), i): l_text.append(body[i]); i += 2
        elif body[i] == '{':
            j, depth = i + 1, 1
            while j < n and depth: depth += {'{': 1, '}': -1}.get(body[j], 0); j += 1
            l_expr.append(body[i + 1:j - 1]); l_text.append('X'); i = j
        else: l_text.append(body[i]); i += 1
    return ''.join(l_text), l_expr

def js_tokens(text):
    # JavaScript or CSS: /* */ and // comments 0, a string 1 plus the code of its ${…}
    count, l_buf, i, n = 0, [], 0, len(text)
    while i < n:
        if text.startswith('/*', i):
            i = text.find('*/', i + 2); i = n if i < 0 else i + 2; l_buf.append(' ')
        elif text.startswith('//', i) and (i == 0 or text[i - 1] in ' \t\n;{}(,'):
            i = text.find('\n', i); i = n if i < 0 else i
        elif text[i] in '\'"`':
            q, j = text[i], i + 1; count += 1
            while j < n and text[j] != q:
                if text[j] == '\\': j += 2; continue
                if q != '`' and text[j] == '\n': break   # no closing quote on the line (an apostrophe in a regex): stop there
                if q == '`' and text.startswith('${', j):
                    e, depth = j + 2, 1
                    while e < n and depth: depth += {'{': 1, '}': -1}.get(text[e], 0); e += 1
                    count += js_tokens(text[j + 2:e - 1]) + 3; j = e; continue
                j += 1
            l_buf.append(' '); i = j + 1
        else: l_buf.append(text[i]); i += 1
    return count + n_words(''.join(l_buf))

def html_tokens(text):
    # Markup: <!-- --> 0, a text between tags 1; a tag: its code, an on…="…" handler as JS; <script>/<style> bodies as JS
    def tag(t): return js_tokens(t) + sum(js_tokens(h) - 1 for _, h in re.findall(r'\bon\w+\s*=\s*(["\'])(.*?)\1', t, re.S))
    count = 0
    for m in re.finditer(r'(<(script|style)\b[^>]*>)(.*?)(</\2\s*>)|(<[^>]*>)|([^<]+)', re.sub(r'<!--.*?-->', ' ', text, flags=re.S), re.S | re.I):
        if m.group(3) is not None: count += tag(m.group(1)) + js_tokens(m.group(3)) + n_words(m.group(4))
        elif m.group(5): count += tag(m.group(5))
        elif m.group(6).strip(): count += 1
    return count

def settings_tokens(text):
    return sum(1 for l in text.splitlines() if l.strip() and not l.lstrip().startswith(('#', '//', ';')))

def tokens(path):
    text = path.read_text(errors='replace')
    first = text.split('\n', 1)[0]
    if path.suffix in ('.sh', '.bash') or (not path.suffix and re.match(r'#!.*\b(ba|z)?sh\b', first)): return sh_tokens(text)
    if path.suffix == '.py' or (not path.suffix and 'python' in first): return py_tokens(text)
    if path.suffix in ('.js', '.mjs', '.ts', '.css'): return js_tokens(text)
    if path.suffix in ('.html', '.htm'): return html_tokens(text)
    return settings_tokens(text)

def lines(path):
    # (lines, code lines): lines not blank, and lines not only a comment (docstrings are not detected here)
    l_line = [l.strip() for l in path.read_text(errors='replace').splitlines() if l.strip()]
    return len(l_line), sum(1 for l in l_line if not l.startswith(('#', '//', '/*', '*', '<!--')))

parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
parser.add_argument('-v', action='store_true', help='one row per file')
parser.add_argument('--weight', type=float, default=2, help='weight of the client files (default 2: twice as many clients)')
parser.add_argument('--shared', nargs='+', type=pathlib.Path, required=True, help='files written once')
parser.add_argument('--client', nargs='*', type=pathlib.Path, default=[], help='files written or copied once per client')
args = parser.parse_args()

print(f'{"tokens":>7} {"weight":>6} {"cost":>7} {"lines":>6} {"code lines":>10} {"tokens/code line":>16}  files')
d_total = {}
for group, weight, l_path in (('shared', 1, args.shared), ('client', args.weight, args.client)):
    l_row = sorted(((tokens(p), *lines(p), str(p)) for p in l_path), reverse=True)
    for tok, nl, ncl, name in l_row if args.v else []:
        print(f'{tok:7} {weight:6g} {tok * weight:7g} {nl:6} {ncl:10} {tok / max(ncl, 1):16.1f}  {name}')
    tok, nl, ncl = (sum(r[k] for r in l_row) for k in range(3))
    d_total[group] = tok * weight
    print(f'{tok:7} {weight:6g} {tok * weight:7g} {nl:6} {ncl:10} {tok / max(ncl, 1):16.1f}  = {group} ({len(l_row)} files)')
print(f'TOTAL COST {sum(d_total.values()):g}  (shared {d_total["shared"]:g} + client {d_total["client"]:g})')
