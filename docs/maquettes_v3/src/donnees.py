# Construit donnees.json (chiffres réels du 14/05 au 16/10/2026) pour la maquette v3.
import pandas as pd, json, sys
a=pd.read_csv('data/avis_propres.csv',encoding='utf-8-sig'); s=pd.read_csv('data/aspects.csv',encoding='utf-8-sig')
a['date']=pd.to_datetime(a.date); a=a[a.date>='2026-05-14']; s=s[pd.to_datetime(s.date)>='2026-05-14']
neg=s[s.etiquette.str.startswith('n')&(s.etiquette!='neutre')]
H=[]
for (h,v),g in a.groupby(['hotel','ville']):
    w=g.groupby(pd.Grouper(key='date',freq='W'))['note'].agg(['mean','size'])
    H.append(dict(nom=h.replace('Kenzi ',''),ville=v,n=int(len(g)),note=round(g.note.mean(),2),
      neg=round((g.note<=2).mean()*100,1),delai=round(float(g.delai_reponse_h.median()),0),
      dist=[int((g.note==k).sum()) for k in range(1,6)],
      sem=[None if pd.isna(x) else round(x,2) for x in w['mean'].tolist()]))
asp=neg.aspect.value_counts().index.tolist()
M={h.replace('Kenzi ',''):{k:int(c) for k,c in g.aspect.value_counts().items()} for h,g in neg.groupby('hotel')}
C={}
for (h,k),g in neg.groupby(['hotel','aspect']):
    g=g[g.phrase.str.len().between(35,150)].sort_values('score'); C[h.replace('Kenzi ','')+'|'+k]=g.phrase.head(2).tolist()
def q(df,n):
    df=df[df.phrase.str.len().between(40,125)].drop_duplicates('phrase')
    return [dict(h=r.hotel.replace('Kenzi ',''),a=r.aspect,t=r.phrase) for r in df.groupby('hotel').head(n).itertuples()]
P=q(s[s.etiquette=='positif'].sort_values('score',ascending=False),7); N=q(neg.sort_values('score'),7)
weeks=sorted(a.groupby(pd.Grouper(key='date',freq='W')).size().index)
json.dump(dict(hotels=H,aspects=asp,mat=M,cell=C,pos=P,neg=N,semaines=[d.strftime('%d/%m') for d in weeks],
  total=int(len(a)),note=round(a.note.mean(),2)),open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
print('ok',len(a),len(P),len(N))

# Détail par semaine (pouls du groupe)
d=json.load(open(sys.argv[1],encoding='utf-8'))
a['wk']=a.date.dt.to_period('W-SUN').dt.end_time.dt.normalize()
neg2=neg.copy(); neg2['wk']=pd.to_datetime(neg2.date).dt.to_period('W-SUN').dt.end_time.dt.normalize()
S=[]
for w,g in a.groupby('wk'):
    ng=neg2[neg2['wk']==w]; top=ng.aspect.value_counts()
    q=None
    if len(top):
        c=ng[(ng.aspect==top.index[0])&ng.phrase.str.len().between(35,140)].sort_values('score')
        if len(c): q=dict(h=c.iloc[0].hotel.replace('Kenzi ',''),t=c.iloc[0].phrase)
    S.append(dict(du=(w-pd.Timedelta(days=6)).strftime('%d/%m'),au=w.strftime('%d/%m'),note=round(g.note.mean(),2),n=int(len(g)),
      ko=int((g.note<=2).sum()),sujet=top.index[0] if len(top) else None,nsujet=int(top.iloc[0]) if len(top) else 0,q=q))
d['pouls']=S
json.dump(d,open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False); print('pouls',len(S))
