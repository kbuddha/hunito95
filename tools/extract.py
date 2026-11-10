import sys, os, unicodedata, logging, glob, re
logging.disable(logging.CRITICAL)
import pdfplumber
def fix(s):
    return ''.join(unicodedata.normalize('NFKC',c) if 0x2E80<=ord(c)<=0x2FDF else c for c in s)
def lines_of(words):
    words=sorted(words,key=lambda w:(round(w['top']),w['x0']))
    L=[];cur=[];top=None
    for w in sorted(words,key=lambda w:w['top']):
        if top is None or abs(w['top']-top)>3:
            if cur:L.append(cur)
            cur=[w];top=w['top']
        else: cur.append(w)
    if cur:L.append(cur)
    return [sorted(l,key=lambda w:w['x0']) for l in L]
def page_text(p):
    W=p.extract_words(x_tolerance=1.5,y_tolerance=2,keep_blank_chars=False,use_text_flow=False)
    mid=p.width/2
    lines=lines_of(W)
    # 줄 단위: 가운데를 가로지르는 단어가 있으면 전체폭, 아니면 좌/우로 나눔
    out=[];left=[];right=[]
    def flush():
        nonlocal left,right
        for l in left: out.append(l)
        for l in right: out.append(l)
        left=[];right=[]
    for l in lines:
        cross=any(w['x0']<mid-4 and w['x1']>mid+4 for w in l)
        if cross: flush(); out.append(' '.join(w['text'] for w in l))
        else:
            a=[w for w in l if w['x1']<=mid+4]; b=[w for w in l if w['x1']>mid+4]
            if a: left.append(' '.join(w['text'] for w in a))
            if b: right.append(' '.join(w['text'] for w in b))
    flush()
    return fix('\n'.join(out))
src,dst=sys.argv[1],sys.argv[2]
os.makedirs(dst,exist_ok=True)
for f in sorted(glob.glob(os.path.join(src,'*.pdf'))):
    n=os.path.basename(f)[:-4]
    with pdfplumber.open(f) as pdf:
        t='\n'.join('<<PAGE %d>>\n'%(i+1)+page_text(p) for i,p in enumerate(pdf.pages))
    open(os.path.join(dst,n+'.txt'),'w',encoding='utf-8').write(t)
    print(n,len(t))
