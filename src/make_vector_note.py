from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from pathlib import Path
import json,csv,math
root=Path(__file__).resolve().parents[1]
out=root/'docs/lehalle_one_page_note.pdf'
s=json.load(open(root/'results/phase2_summary.json'))
width=list(csv.DictReader(open(root/'results/tables/phase2_width_sensitivity.csv')))
W,H=A4
navy=HexColor('#17365D'); dark=HexColor('#1F2933'); grey=HexColor('#5A6573'); grid=HexColor('#D8DEE6'); blue=HexColor('#2E6F9E'); red=HexColor('#A64B4B'); pale=HexColor('#F7F9FB')
c=canvas.Canvas(str(out),pagesize=A4,pageCompression=1)

def t(x,y,text,size=8.5,bold=False,color=dark):
    c.setFillColor(color); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size); c.drawString(x,y,text)
def tr(x,y,text,size=8.5,bold=False,color=dark):
    c.setFillColor(color); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size); c.drawRightString(x,y,text)
def tc(x,y,text,size=8.5,bold=False,color=dark):
    c.setFillColor(color); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size); c.drawCentredString(x,y,text)

m=38
t(m,H-45,"Options as anticipative factors: where does the smile's information live?",15.5,True,navy)
t(m,H-62,'Exploratory Phase II note - NIFTY weekly options, one non-overlapping observation per expiry',8.5,False,grey)
t(m,H-86,'Question.',8.5,True,dark); t(m+42,H-86,'After conditioning on the ATM option-implied movement scale, does cross-strike smile geometry',8.5,False,dark)
t(m,H-98,'add information about the size of the future move, or about which side of the distribution is tilted?',8.5,False,dark)

pa_top=H-128
t(m,pa_top,'A. Incremental predictive content of smile geometry',10.5,True,dark)
left=188; right=W-38; xmin=-0.125;xmax=0.025
xmap=lambda v:left+(v-xmin)/(xmax-xmin)*(right-left)
for v in [-.12,-.09,-.06,-.03,0,.02]:
    x=xmap(v); c.setStrokeColor(HexColor('#E5E9EF')); c.setLineWidth(.5); c.line(x,pa_top-104,x,pa_top-10); tc(x,pa_top-117,f'{v:+.2f}',6.5,False,grey)
c.setStrokeColor(HexColor('#7B8794'));c.setLineWidth(1);c.line(xmap(0),pa_top-104,xmap(0),pa_top-10)
labels=[('Any large move |z| >= 1','two_sided_1sigma','No gain'),('Downside tail z <= -1','down_1sigma','Tiny'),('Upside tail z >= +1','up_1sigma','7.5% lower Brier'),('Direction, given a large move*','down_given_1sigma_breach','14.9% lower Brier*')]
boot={r['event']:r for r in s['bootstrap'] if r['metric']=='brier'}; cboot=next(r for r in s['conditional_direction_bootstrap'] if r['metric']=='brier')
for i,(lab,event,note) in enumerate(labels):
    y=pa_top-24-i*25
    t(m,y-2,lab,7.4,False,dark)
    r=cboot if event=='down_given_1sigma_breach' else boot[event]; d=r['mean_diff_plus_shape_minus_level'];lo=r['ci_lo_95'];hi=r['ci_hi_95']; col=blue if d<0 else red
    c.setStrokeColor(col);c.setLineWidth(1.5);c.line(xmap(lo),y,xmap(hi),y);c.line(xmap(lo),y-3,xmap(lo),y+3);c.line(xmap(hi),y-3,xmap(hi),y+3);c.setFillColor(col);c.circle(xmap(d),y,3.3,fill=1,stroke=0)
    if d<0: tr(xmap(d)-5,y-2,note,6.6,i>=2,dark)
    else: t(xmap(d)+5,y-2,note,6.6,False,dark)
tc((left+right)/2,pa_top-132,'Change in out-of-sample Brier after adding smile shape (negative = better)',7.2,False,grey)

pb=pa_top-162
t(m,pb,'B. Width robustness: direction is more stable than magnitude',10.5,True,dark)
widths=[1,2,3,4,5,6,8,10]; events=[x[1] for x in labels]; dct={(r['event'],int(r['width_index'])):float(r['diff_brier_plus_shape_minus_level']) for r in width}; vmax=max(abs(v) for v in dct.values())
hleft=192; cw=38; ch=19
for j,w in enumerate(widths): tc(hleft+j*cw+17,pb-13,str(w),6.5,True,grey)
def blend(v):
    a=min(abs(v)/vmax,1); target=(46,111,158) if v<0 else (166,75,75); base=(247,249,251); rgb=[int(base[k]*(1-a)+target[k]*a) for k in range(3)];return HexColor('#%02x%02x%02x'%tuple(rgb))
for i,(lab,event,_) in enumerate(labels):
    y=pb-27-i*ch; t(m,y+5,lab,6.8,False,dark)
    for j,w in enumerate(widths):
        v=dct[(event,w)]; x=hleft+j*cw; c.setFillColor(blend(v));c.setStrokeColor(white);c.rect(x,y,cw-2,ch-2,fill=1,stroke=1); tc(x+(cw-2)/2,y+5.2,f'{v:+.3f}',5.5,True,white if abs(v)>.45*vmax else dark)
cy=pb-118
cards=[('Magnitude','0 / 8 widths improve',red),('Upside tail','8 / 8 widths improve',blue),('Tail direction*','8 / 8 widths improve',blue)]
for i,(head,val,col) in enumerate(cards):
    x=m+i*166; c.setFillColor(pale);c.setStrokeColor(grid);c.roundRect(x,cy,152,29,4,fill=1,stroke=1);t(x+8,cy+17,head,6.5,True,grey);t(x+8,cy+6,val,8,True,col)

te=cy-30
t(m,te,'Compact out-of-sample readout',10.5,True,navy)
headers=['Task','N/events','Brier level','Brier +shape','Delta','AUC level -> shape','Widths']
xs=[m,194,248,307,367,415,515]; widthscol=[156,54,59,60,48,100,42]
rowy=te-18
c.setFillColor(navy);c.rect(m,rowy,519,18,fill=1,stroke=0)
for x,wid,h in zip(xs,widthscol,headers): tc(x+wid/2,rowy+5.5,h,6.2,True,white)
metrics={}
for e in ['two_sided_1sigma','down_1sigma','up_1sigma']:
    rs=[r for r in s['headline_metrics'] if r['event']==e]; b=next(r for r in rs if r['model']=='level_controls');sh=next(r for r in rs if r['model']=='plus_shape');metrics[e]=(b,sh)
rows=[('Any one-scale breach','two_sided_1sigma'),('Downside breach','down_1sigma'),('Upside breach','up_1sigma')]
vals=[]
for lab,e in rows:
    b,sh=metrics[e];vals.append([lab,f"{b['n']} / {b['events']}",f"{b['brier']:.4f}",f"{sh['brier']:.4f}",f"{sh['brier']-b['brier']:+.4f}",f"{b['auc']:.3f} -> {sh['auc']:.3f}",f"{s['width_sign_counts'][e]['n_brier_improvements']}/8"])
b,sh=s['conditional_direction']; vals.append(['Direction given breach*',f"{b['n']} / {b['events']}",f"{b['brier']:.4f}",f"{sh['brier']:.4f}",f"{sh['brier']-b['brier']:+.4f}",f"{b['auc']:.3f} -> {sh['auc']:.3f}",'8/8'])
for i,row in enumerate(vals):
    y=rowy-(i+1)*18;c.setFillColor(white if i%2==0 else pale);c.setStrokeColor(grid);c.rect(m,y,519,18,fill=1,stroke=1)
    for j,(x,wid,v) in enumerate(zip(xs,widthscol,row)):
        if j==0:t(x+4,y+5.2,v,6.4,False,dark)
        else:tc(x+wid/2,y+5.2,v,6.2,False,dark)
ry=rowy-4*18-24
t(m,ry,'Readout.',8.2,True,dark);t(m+38,ry,'Smile shape does not improve two-sided one-scale breach probability (0/8 widths). The strongest',7.8,False,dark)
t(m,ry-11,'OOS signal is directional: upside-breach Brier falls 0.1227 -> 0.1134, and all 8/8 widths improve it.',7.8,False,dark)
t(m,ry-22,'Conditional direction also improves at 8/8 widths, but that N=23 result conditions on a future breach and is diagnostic.',7.8,False,dark)
t(m,ry-39,'Interpretation.',8.2,True,dark);t(m+55,ry-39,'The pattern is consistent with ATM level summarizing forward risk magnitude while cross-strike state prices',7.8,False,dark)
t(m,ry-50,'may encode distributional tilt. This is hypothesis-generating, not conclusive; next: theta vs theta + {rho, psi, RR, BF}.',7.8,False,dark)
c.setFillColor(HexColor('#EEF2F6'));c.rect(m,34,519,1,fill=1,stroke=0)
t(m,20,'73 evaluation expiries; 23 one-scale breaches. Aggregate outputs/code reproducible; licensed row-level market data not redistributed.',6.4,False,grey)
c.showPage();c.save();print(out, out.stat().st_size)
