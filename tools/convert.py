import json, re, sys, os, glob, random
TXT, REC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
rec = json.load(open(REC, encoding='utf-8'))['기록']
CIR = '①②③④⑤⑥'
RADMAP = str.maketrans({'⺒':'巳','⻝':'食','⻑':'長','⺠':'民','⻄':'西','漢':'漢'})
CJK = re.compile(r'[ㄱ-ㆎ가-힣一-鿿㐀-䶿]')
def smart_join(lines):
    out = ''
    for l in lines:
        l = l.strip()
        if not l: continue
        if not out: out = l; continue
        if CJK.match(out[-1]) and CJK.match(l[0]) and not re.match(r'^[ㄱ-ㅎ]\s', l): out += l
        else: out += ' ' + l
    return out
JUNK = re.compile(r'^(<<PAGE \d+>>|\d+\s*/\s*\d*|\d+|채점 후 .*|.*30분\s*·\s*\d+문항.*)$')
def regions(text):
    L = text.split('\n')
    end = len(L)
    for i, l in enumerate(L):
        if i > 5 and (re.match(r'^\s*(2부|정답표|빠른 정답|정답 ?·)', l)):
            end = i; break
    exp_start = None
    for i in range(end, len(L)):
        if re.match(r'^\s*(짧은 )?해설\s*$', L[i]) or re.match(r'^\s*(짧은 해설|해설)\b', L[i]):
            exp_start = i + 1; break
    exp_end = len(L)
    if exp_start:
        for i in range(exp_start, len(L)):
            if re.match(r'^\s*(오늘의 1·3·7|마법·반복 목록|마법 목록|핵심\s*$|💡)', L[i]): exp_end = i; break
    return L[:end], (L[exp_start:exp_end] if exp_start else [])
def blocks(lines, pat):
    cands = [(i, int(m.group(1))) for i, l in enumerate(lines) for m in [re.match(pat, l)] if m]
    acc = []; exp = 1
    for k, (i, n) in enumerate(cands):
        if n == exp or (exp < n <= exp + 60 and any(c[1] == n + 1 for c in cands[k+1:k+8])):
            acc.append((i, n)); exp = n + 1
    res = {}
    for k, (i, n) in enumerate(acc):
        j = acc[k+1][0] if k + 1 < len(acc) else len(lines)
        res[n] = lines[i:j]
    return res
def all_blocks(lines, pat):
    idx = [(i, int(m.group(1))) for i, l in enumerate(lines) for m in [re.match(pat, l)] if m]
    out = [(n, lines[i:(idx[k+1][0] if k + 1 < len(idx) else len(lines))]) for k, (i, n) in enumerate(idx)]
    nums = {n for n, _ in out}; res = []
    for n, bl in out:
        cut = None
        for j in range(1, len(bl)):
            if re.match(r'^\s*\[[^\]]*(한의학|생리학|생물|한자)', bl[j]) and any('①' in x for x in bl[:j]) and (n + 1) not in nums:
                cut = j; break
        if cut: res += [(n, bl[:cut]), (n + 1, [str(n + 1) + ' ' + bl[cut]] + bl[cut + 1:])]; nums.add(n + 1)
        else: res.append((n, bl))
    return res
NORM = lambda s: re.sub(r'[\s\W_①-⑥]', '', re.sub(r'<[^>]+>', '', s))
def grams(s): return {s[i:i+2] for i in range(len(s) - 1)}
def score(concept, body):
    c = grams(NORM(concept)[:60]); b = grams(NORM(body)[:200])
    return len(c & b) / max(1, len(c))
def pair_layout(q):
    # 짝 맞추기: (1)… 과 ㄱ… 항목을 따로 모아 두 묶음으로
    toks = re.split(r'(\(\d\)|(?:(?<=\s)|^)[ㄱ-ㅎ](?=\s))', q)
    stem = toks[0].strip(); L = []; R = []; cur = None
    for i in range(1, len(toks), 2):
        mk = toks[i]; tx = re.sub(r'(→|_{2,})', ' ', toks[i + 1] if i + 1 < len(toks) else '')
        tx = re.sub(r'\s{2,}', ' ', tx).strip(' ,·')
        (L if mk.startswith('(') else R).append(mk + ' ' + tx if not mk.startswith('(') else mk + tx)
    if len(L) < 2 or len(R) < 2: return q
    return stem + '\n' + '\n'.join(L) + '\n\n' + '   '.join(R)
TOK = re.compile(r'(?:\(\d\)\s*[ㄱ-ㅎ]\s*)+|[①-⑥]|[OX]\*?')
def norm_pair(a): return ' '.join('(%s)%s' % m for m in PAIR.findall(a))
def parse_table(raw):
    m = re.search(r'(?m)^[^\n]{0,12}정답표[^\n]{0,8}$', raw)
    if not m: return {}
    i = m.start()
    seg = raw[i:]
    for stop in ('450제', '짧은해설', '\n해설', '해설\n', '오늘의1·3·7'):
        j = seg.find(stop, 5)
        if j > 0: seg = seg[:j]
    lines = [l for l in seg.split('\n')[1:] if l.strip()]
    res = {}
    grid = any(re.fullmatch(r'(\d{1,3} )+\d{1,3}', l.strip()) for l in lines)
    if grid:
        k = 0
        while k < len(lines):
            l = lines[k].strip()
            if re.fullmatch(r'(\d{1,3} )+\d{1,3}', l):
                nums = [int(x) for x in l.split()]; body = []
                k += 1
                while k < len(lines) and not re.fullmatch(r'(\d{1,3} )+\d{1,3}', lines[k].strip()):
                    body.append(lines[k]); k += 1
                toks = []
                raw_toks = []
                for t in TOK.findall(' '.join(body)):
                    if t.startswith('('): raw_toks += [x for x in re.split(r'(?=\(1\))', t) if x.strip()]
                    else: raw_toks.append(t)
                for t in raw_toks:
                    if t.startswith('(') and toks and toks[-1].startswith('(') and not t.startswith('(1)'): toks[-1] += t
                    else: toks.append(t)
                if len(toks) == len(nums):
                    for n, t in zip(nums, toks): res[n] = t
            else: k += 1
    else:
        flat = re.sub(r'\n(?=\(?\d?\)?[ㄱ-ㅎ(])', '', '\n'.join(lines))
        flat = re.sub(r'\((\d)\)\n', r'(\1)', flat)
        for m in re.finditer(r'(?<![\d(])(\d{1,3})\s*((?:\(\d\)\s*[ㄱ-ㅎ]\s*)+|[①-⑥]|[OX]\*?)', flat):
            res.setdefault(int(m.group(1)), m.group(2))
    return {n: (norm_pair(t) if t.startswith('(') else t.strip()) for n, t in res.items()}
def clean_q(s):
    s = re.sub(r'^\d{1,3}(\.\s*|\s+(?=\[))', '', s)
    s = re.sub(r'\[[^\]]{0,40}\]', '', s)
    s = re.sub(r'⚠\s*\d회', '', s)
    s = re.sub(r'답\s*[:：]\s*_+', '', s)
    s = re.sub(r'_{3,}', '____', s)
    s = re.sub(r'\(\s*O\s*/\s*X\s*\)', '', s)
    s = re.sub(r'^\s*(한의학|생물학|생물|생리학)\s+', '', s.strip())
    return re.sub(r'\s{2,}', ' ', s).strip()
PAIR = re.compile(r'\((\d)\)\s*([ㄱ-ㅎ])')
def pair_choices(ans, letters, seed):
    m = PAIR.findall(ans)
    if len(m) < 2: return None
    keys = [k for k, _ in m]; vals = [v for _, v in m]
    rnd = random.Random(seed)
    pool = sorted(set(letters) | set(vals))
    fmt = lambda vs: ' '.join('(%s)%s' % (k, v) for k, v in zip(keys, vs))
    right = fmt(vals); seen = {right}; outs = []
    tries = 0
    while len(outs) < 3 and tries < 200:
        tries += 1
        vs = vals[:]
        if len(set(vals)) == len(vals) and rnd.random() < .8:
            a, b = rnd.sample(range(len(vs)), 2); vs[a], vs[b] = vs[b], vs[a]
            if rnd.random() < .4:
                a, b = rnd.sample(range(len(vs)), 2); vs[a], vs[b] = vs[b], vs[a]
        else:
            for _ in range(rnd.choice([1, 2])):
                i = rnd.randrange(len(vs)); vs[i] = rnd.choice([p for p in pool if p != vs[i]] or pool)
        f = fmt(vs)
        if f not in seen: seen.add(f); outs.append(f)
    if len(outs) < 3: return None
    ch = outs + [right]; rnd.shuffle(ch)
    return ch, ch.index(right) + 1
stats = {}; sets = []; FIXES = []
for f in sorted(glob.glob(os.path.join(TXT, '*.txt'))):
    day = re.search(r'(\d{4}-\d\d-\d\d)', f).group(1)
    r = rec.get(day)
    if not r or not r.get('항목'):
        # 기록이 없는 날: PDF에서 직접 (섹션 제목으로 과목, 빠른 정답표로 정답)
        t0 = open(f, encoding='utf-8').read().translate(RADMAP)
        ql0, _ = regions(t0)
        tb0 = parse_table(open(os.path.join(os.path.dirname(OUT) or '.', 'raw_' + os.path.basename(f)), encoding='utf-8').read().translate(RADMAP))
        secs = []; cur = '한의학'
        for i, l in enumerate(ql0):
            m = re.match(r'^\s*(?:[ⅠⅡⅢⅣⅤ]|[A-E])\.\s*(한의학|생물학|생물|한자|생리학)', l)
            if m: cur = m.group(1)
            secs.append(cur)
        bl0 = blocks(ql0, r'^\s*(\d{1,3})(?:\.\s*|\s+\[)')
        pos = {n: next(i for i, l in enumerate(ql0) if l is b[0]) for n, b in bl0.items()}
        r = {'파일': os.path.basename(f)[:-4] + '.pdf', '항목': [{'문항번호': n, '과목': secs[pos[n]], '개념': clean_q(' '.join(b))[:60], '정답': tb0[n]} for n, b in bl0.items() if n in tb0]}
        if not r['항목']: stats[day] = 'no record / no table'; continue
    items_rec = {int(x['문항번호']): x for x in r['항목'] if isinstance(x, dict) and re.fullmatch(r'\d+', str(x.get('문항번호', '')))}
    text = open(f, encoding='utf-8').read().translate(RADMAP)
    qlines, elines = regions(text)
    TABLE = parse_table(open(os.path.join(os.path.dirname(OUT) or '.', 'raw_' + os.path.basename(f)), encoding='utf-8').read().translate(RADMAP))
    AB = all_blocks(qlines, r'^\s*(\d{1,3})(?:\.\s*|\s+\[)')
    eb = blocks(elines, r'^\s*(\d{1,3})[\s.)]')
    blank = r.get('백지인출') if isinstance(r.get('백지인출'), dict) else {}
    out = []; st = {'mc': 0, 'ox': 0, 'pair': 0, 'short': 0, 'skip_hanja': 0, 'noq': 0}
    for n in sorted(items_rec):
        x = items_rec[n]; subj = x.get('과목', '')
        if subj.startswith('한자'): st['skip_hanja'] += 1; continue
        ans = str(x.get('정답', '')).strip()
        con = x.get('개념', '')
        same = [(score(con, ' '.join(bl)), bn, bl) for bn, bl in AB if bn == n]
        other = max([(score(con, ' '.join(bl)), bn, bl) for bn, bl in AB if bn != n] or [(0, 0, [])], key=lambda t: t[0])
        sb = max(same, key=lambda t: t[0]) if same else None
        if sb and other[1] in items_rec and other[1] != n and (score(items_rec[other[1]].get('개념', ''), ' '.join(other[2])) >= 0.5 or other[0] - sb[0] < 0.5): other = (0, 0, [])
        if sb and (sb[0] >= 0.6 or (len(same) == 1 and not (other[0] >= 0.75 and other[0] - sb[0] > 0.4))):
            best = sb
        elif other[0] >= 0.6:
            best = other
        else:
            st['noq'] += 1; continue
        if len(NORM(con)) >= 14 and best[0] < 0.35:
            if other[0] >= 0.6: best = other
            else: st['noq'] += 1; continue
        raw = best[2]; matched_n = best[1]
        ta = TABLE.get(matched_n)
        if ta:
            ra = norm_pair(ans) if PAIR.findall(ans) else (ans.strip()[:1] if ans else '')
            if ra and ra != ta.rstrip('*'):
                st['fix'] = st.get('fix', 0) + 1
                FIXES.append({'날짜': day, '문항번호': x.get('문항번호'), 'PDF번호': matched_n, '기존정답': ans, '바른정답': ta.rstrip('*'), '_body': raw})
            ans = ta
        else: st['notab'] = st.get('notab', 0) + 1
        raw = [l for l in raw if not JUNK.match(l.strip())]
        body = smart_join(raw)
        # 보기 분리
        it = {'pn': best[1], 'id': str(n), 'tag': '생물' if subj.startswith('생물') else subj, 'stage': x.get('태그') or x.get('단계') or '',
              'concept': re.sub(r'<[^>]+>', '', str(x.get('개념', '')))[:80], 'src': re.sub(r'<[^>]+>', '', str(x.get('출처', '')))[:60]}
        if any(c in body for c in CIR[:4]) and re.match(r'^\s*[①-⑥]', ans):
            first = min(body.index(c) for c in CIR if c in body)
            q = body[:first]; rest = body[first:]
            parts = re.split(r'([①-⑥])', rest)[1:]
            ch = []; last = -1
            for i in range(0, len(parts), 2):
                ci = CIR.index(parts[i])
                if ci <= last: break
                last = ci; ch.append(re.split(r'\s\[[^\]]*(?:·|D\+|마법|미풀이|생리|생물|한의)', parts[i + 1])[0].strip())
            ai = CIR.index(ans.strip()[0]) + 1
            if len(ch) >= 2 and ai <= len(ch) and all(ch):
                it.update(q=clean_q(q), ch=ch, a=ai); st['mc'] += 1
            else:
                it.update(q=clean_q(body), a=ans); st['short'] += 1
        elif re.fullmatch(r'[OXＯ×]\*?', ans.replace(' ', '')) or (('O / X' in body or 'O/X' in body or 'OX' in body[:40]) and ans[:1] in 'OX'):
            it.update(q=clean_q(body), ch=['O', 'X'], a=1 if ans.strip()[0] in 'OＯ' else 2); st['ox'] += 1
        elif len(PAIR.findall(ans)) >= 2:
            letters = re.findall(r'(?:^|\s)([ㄱ-ㅎ])\s', ' ' + body + ' ')
            pc = pair_choices(ans, letters, hash(day + str(n)) & 0xffff)
            q = pair_layout(clean_q(body))
            if pc: it.update(q=q, ch=pc[0], a=pc[1]); st['pair'] += 1
            else: it.update(q=q, a=ans); st['short'] += 1
        else:
            it.update(q=clean_q(body), a=ans or '(정답 기록 없음)'); st['short'] += 1
        e = eb.get(n)
        if e and score(it['q'][:60], ' '.join(e)) < 0.08 and score(ans, ' '.join(e)) < 0.5: e = None
        if e:
            ex = re.sub(r'^\s*\d{1,3}[\s.)]\s*', '', smart_join([l for l in e if not JUNK.match(l.strip())]))
            ex = re.sub(r'^정답\s*\S+(\s*\([1-9]\)\s*[ㄱ-ㅎ])*\s*(\[[^\]]*\]\s*)*[—-]?\s*', '', ex)
            ex = re.split(r'450제 해설|<<PAGE', ex)[0]
            it['exp'] = ex[:500]
        if 'ch' not in it and str(it['a']).startswith('(1)') and (it.get('exp') or '').startswith('(1)'):
            it['a'] = re.split(r'\s[—-]\s', it['exp'])[0].strip()
        if '*' in ans or 'Claude 추정' in (it.get('exp') or ''): it['exp'] = (it.get('exp') or '') + ' (정답 확인 필요)'
        if not it['q']: st['noq'] += 1; continue
        out.append(it)
    stats[day] = st
    if not out: continue
    bl = [{'id': k, 't': re.sub(r'<[^>]+>', '', str(v))} for k, v in blank.items()]
    m, d = int(day[5:7]), int(day[8:])
    sets.append({'id': 'past-' + day, 'day': day, 'title': '%d/%d 복습문제 · %d문항' % (m, d, len(out)), 'subj': 'mix', 'blank': bl, 'items': out,
                 'note': '지난 복습문제 PDF(%s)를 객관식으로 옮긴 것. 짝 맞추기는 올바른 조합 고르기로 바꿨고, 빈칸 문제는 주관식(정답 보고 스스로 채점)으로 남겼어요.' % r.get('파일', '')})
for fx in FIXES:
    body = smart_join([l for l in fx.pop('_body') if not JUNK.match(l.strip())])
    fx['문제'] = clean_q(re.split(r'[①-⑥]', body)[0])[:70]
    m = re.match(r'^([①-⑥])', fx['바른정답'])
    if m:
        parts = re.split(r'([①-⑥])', body)
        for i in range(1, len(parts) - 1, 2):
            if parts[i] == m.group(1): fx['바른답내용'] = parts[i + 1].strip()[:40]; break
json.dump({'설명': 'PDF 빠른 정답표와 다른 _출제기록.json 정답 목록 (보기를 섞은 뒤 기록이 갱신되지 않은 것으로 보임). PDF 정답표 기준이 맞음을 내용으로 확인함. 문항번호 = _출제기록의 번호, PDF번호 = PDF 문제지 번호.', '수정': FIXES}, open(os.path.join(os.path.dirname(OUT) or '.', 'fixes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(sets, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
for k, v in stats.items(): print(k, v)
print('sets', len(sets), 'items', sum(len(s['items']) for s in sets), 'bytes', os.path.getsize(OUT))
