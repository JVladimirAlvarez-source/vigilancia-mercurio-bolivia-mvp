"""Synthetic demonstration only. All coefficients/probabilities unless explicitly cited
are [SUPUESTO_SIMULACION_MVP]. No patient data, no clinical validation.
Run: python generate_synthetic_bolivia.py --out .
Parquet requires pyarrow or fastparquet; CSV always written.
"""
import argparse, json, warnings, hashlib, scipy, tempfile, io
from scipy.stats import kstest, spearmanr, binomtest
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm
from scipy.optimize import brentq

N=1500
SYM='nauseas vomito disfagia gingivitis salivacion_excesiva estomatitis_mercurial sabor_metalico ribete_gilbert diente_letulle hepatomegalia hematuria prurito descamacion_piel erupcion_cutanea irritacion_ocular conjuntivitis disminucion_campo_visual opresion_ardor_torax convulsiones disfuncion_renal depresion ansiedad irritabilidad disartria ataxia polineuropatia_periferica adormecimiento temblor_distal disnea tos'.split()
CLIN=[f'clin_{i}_{s}' for i,s in enumerate(SYM,35)]
LAB='tipo_muestra fecha_toma_muestra fecha_envio_lab EXT_67b_concentracion_hg_resultado EXT_67c_unidad_medida EXT_67d_longitud_segmento_cabello_cm lab_hg_cabello_ug_g lab_hg_orina_ug_g_cr lab_hg_sangre_ug_l'.split()
Y='clasificacion_guia537 y_mehg_cabello_bolivia y_mehg_cabello_5 y_hg_urinario_hbm2 y_hg_urinario_guia537 flag_anomalia_real'.split()
PRE='fecha_notificacion departamento municipio localidad_comunidad establecimiento_salud antecedente_exposicion_hg tipo_notificacion captado_en edad sexo EXT_10b_peso_corporal_kg ocupacion procedencia residencia_actual embarazo_actual lactancia_actual numero_hijos antecedente_aborto_espontaneo fecha_exposicion antecedente_exposicion_anterior_anos lugar_probable_exposicion ocupacion_momento_exposicion tiempo_exposicion_horas_equiv EXT_27b_quema_amalgama_frecuencia EXT_27c_quema_espacio_cerrado_o_vivienda EXT_27d_uso_retorta via_respiratoria via_dermica via_oral via_desconocida tipo_ocupacional tipo_accidental tipo_ambiental presencia_empresas_mineras consumo_pescado_rio frecuencia_consumo_pescado_dias EXT_32b_especies_piscivoras_alto_hg EXT_32c_frecuencia_piscivoros_30d EXT_32d_tamano_porcion_gramos antecedente_familiar_mineria tipo_parentesco'.split()+CLIN+['EXT_64b_fecha_inicio_sintomas']
# Administrative fields excluded from learning; clinical renal dysfunction is simulated as pre-lab history.
FEATURES=[c for c in PRE if c not in ['fecha_notificacion','departamento','municipio','localidad_comunidad','establecimiento_salud','procedencia','residencia_actual','tipo_notificacion','captado_en']]

# All non-empirical coefficients are [SUPUESTO_SIMULACION_MVP].
# Sources: ATSDR 2024 tables 5-25, 5-33; PMID 19004394 (Beni);
# PMID 27449026 (Colombia); PMID 31627842 (Peru); DOI 10.1016/j.jfca.2025.108840.
# Lebel PMID 9756677; Dolbec PMID 10787135; Passos PMID 18797727:
# directional evidence only, not binary symptom ORs.
def sig_iqr(q1,q3): return np.log(q3/q1)/(2*norm.ppf(.75))
def sig_mean(m,mean): return np.sqrt(2*np.log(mean/m))

SEED=42
# FALLBACK: design probabilities, not population estimates; Feingold PMID 31627842.
COHORTS=['control','MeHg','Hg2','Hg0','mixto'] # Hg2 internal legacy alias: Peru miner, NOT divalent species
COHORT_LABELS=dict(zip(COHORTS,['Control EE.UU.','Ribereño Beni','Minero Madre de Dios','Quemador Antioquia','Mixto']))
PROBS=[.15,.30,.15,.25,.15]
# Immutable ordered schema from v3, not independently certified official field order.
SCHEMA=[c for c in PRE if c not in ['via_respiratoria','via_dermica','via_oral','via_desconocida','tipo_ocupacional','tipo_accidental','tipo_ambiental']]+[c for c in LAB if not c.startswith('lab_')]+['via_exposicion','tipo_exposicion','nombre_apellido','ci','telefono','nombre_padres_apoderados','residencia_anterior','nombre_apellido_notificador','cargo_notificador','observaciones','firma']
def effect_to_logit(delta_y, sd_latent=1., adverse_direction=1.):
 """FALLBACK: standardized proxy, not an empirical binary log odds; sign oriented to harm."""
 if sd_latent<=0: raise ValueError('sd_latent must be positive')
 return adverse_direction*delta_y/sd_latent

def latent_layer(r,n):
 """FALLBACK: demographic design; no representative Bolivia microdata available."""
 g=r.choice(COHORTS,n,p=PROBS); m=np.isin(g,['MeHg','mixto']); v=np.isin(g,['Hg0','mixto','Hg2']); i=g=='Hg2'; control=g=='control'
 child=r.random(n)<np.where(v,.12,.28)
 age=np.where(child,np.clip(r.poisson(10,n),2,17),np.clip(r.poisson(39,n),18,80)); female=r.random(n)<.52
 fertile=female&(age>=15)&(age<=49); preg=fertile&(r.random(n)<.15); lact=fertile&~preg&(r.random(n)<.15)
 height=np.clip(np.where(child,75+5.2*age,162+11*(~female))+r.normal(0,5,n),85,195)
 weight=np.round(np.clip(np.where(child,3.3*age+7,65+7*(~female))+r.normal(0,6,n),10,125),1)
 bmi=weight/(height/100)**2
 return locals()

def exposure_layer(r,n,z):
 """FUENTE: Feingold PMID 31627842; Loayza DOI 10.1016/j.jfca.2025.108840. FALLBACK: hurdle parameters."""
 g,m,v,i,control,child,weight=[z[k] for k in ['g','m','v','i','control','child','weight']]
 fish=(r.random(n)<np.where(m,.97,.55)).astype(int)
 freq=np.where(fish,np.clip(np.rint(r.gamma(3,np.where(m,6,1.7),n)),1,30),0).astype(int)
 pred=r.binomial(freq,np.where(m,.65,.25)); portion=np.where(fish,np.round(np.clip(weight*2*r.lognormal(0,.28,n),30,300)),0)
 return locals()

def biomarker_layer(r,n,g,scores,anchors):
 """FUENTE: NHANES ATSDR 2024; PMID 19004394, 27449026, 22926732, 31627842. FALLBACK: conditional score slopes and residual dependence."""
 true=np.zeros((n,3)); common=r.normal(size=n)
 for cohort,params in anchors.items():
  mask=g==cohort
  for j,(med,sd) in enumerate(params):
   q=scores[mask,j]; q=q-q.mean(); q=q*min(1,.65*sd/max(q.std(),1e-9))
   residual=np.sqrt(max(sd**2-q.var(),1e-8))*(.30*common[mask]+np.sqrt(1-.30**2)*r.normal(size=mask.sum()))
   true[mask,j]=np.exp(np.log(med)+q+residual)
 return true

def clinical_layer(r,n,control,dose,age,base,beta,domains):
 """FUENTE: Lebel PMID 9756677, Dolbec PMID 10787135 directional only. FALLBACK: all symptom slopes/baselines and random effects."""
 noise=(r.random(n)<.15); shared=r.normal(0,.45,n); individual=r.normal(0,.30,(n,30)); symptoms=np.zeros((n,30),int); intercept=[]
 for j,k in enumerate(domains):
  x=beta[j]*dose[k]+.65*noise+shared+individual[:,j]+.15*(age>60)
  alpha=brentq(lambda a: expit(a+x[control]).mean()-base[j],-20,10); intercept.append(alpha)
  symptoms[:,j]=r.random(n)<expit(alpha+x)
 return symptoms,intercept,shared,individual

def perturbation_layer(r,capture,position,hidden=0):
 """FUENTE: Rubin 1976 DOI 10.1093/biomet/63.3.581 (mechanism only). FALLBACK: rates unmeasured locally."""
 return r.random(len(capture))<expit(-3.0+.8*capture+.6*position+.55*hidden)

def generate(out, *, keyed=False):
 r=np.random.default_rng(SEED); n=N
 def bern(p): return (r.random(n)<p).astype(int)
 def logn(m,s): return np.exp(np.log(m)+s*r.normal(size=n))
 def date(x): return pd.Series(pd.Timestamp('2026-11-01')+pd.to_timedelta(x,unit='D'))
 z=latent_layer(r,n); e=exposure_layer(r,n,z)
 g,m,v,i,control,child,age,female,fertile,preg,lact,weight,height,bmi=[z[k] for k in ['g','m','v','i','control','child','age','female','fertile','preg','lact','weight','height','bmi']]
 fish,freq,pred,portion=[e[k] for k in ['fish','freq','pred','portion']]
 rural=bern(np.where(control,.35,.75)).astype(bool); site=r.choice(3,n); dep=np.array(['La Paz','Beni','La Paz'])[site]; mun=np.array(['Guanay','Rurrenabaque','La Paz'])[site]; loc=np.array(['SINTETICA_A','SINTETICA_B','SINTETICA_C'])[site]
 # Loayza 2026: high-Hg fish arithmetic mean 1.9, SD 1.0 ug/g wet weight; low fish 0.25 assumed.
 sigma=np.sqrt(np.log1p((1/1.9)**2)); high=r.lognormal(np.log(1.9)-sigma**2/2,sigma,n); low=np.minimum(logn(.25,.45),.499)
 edi=(pred*portion*high+(freq-pred)*portion*low)*.9/(30*weight)
 burn=np.where(v & ~child,np.rint(r.gamma(2,4,n)).astype(int),np.where(v,np.rint(r.gamma(1,1,n)).astype(int),r.binomial(1,.03,n))); closed=bern(.5)*(burn>0); retort=bern(.35)*(burn>0)
 hours=np.round(np.where(v|i,logn(18,.9),logn(1,.8)),1); hours=np.where(control,0,np.where(burn>0,hours*burn, np.where(i,hours,0)))
 days=np.where(control,0,np.clip(r.exponential(32,n).astype(int),0,365)); ongoing=bern(.55).astype(bool); days=np.where(ongoing,0,days)
 years=np.minimum(age,np.where(control,0,r.integers(0,16,n))); notif=date(-r.integers(0,180,n)); exposure=notif-pd.to_timedelta(days,unit='D')
 # SCM: log biomarkers = cohort location + centered exposure score + residual.
 # Published summaries anchor conditional marginal distributions, not individual causal effects.
 # Control urine median censored: estimate mu from P75/P95, not a measured median.
 cu_sigma=np.log(.962/.362)/(norm.ppf(.95)-norm.ppf(.75)); cu_mu=np.log(.362)-cu_sigma*norm.ppf(.75)
 anchors={'control':[(.20,.65),(np.exp(cu_mu),cu_sigma),(.580,np.log(3.87/.580)/norm.ppf(.95))],
 'MeHg':[(4.,sig_mean(4.,5.3)),(.55,.85),(7.4,.85)],
 'mixto':[(1.60,sig_mean(1.60,2.24)),(3.9,sig_iqr(1.3,9.6)),(7.,sig_iqr(3.4,11.))],
 'Hg0':[(.8,.85),(3.9,sig_iqr(1.3,9.6)),(7.,sig_iqr(3.4,11.))],
 'Hg2':[(1.6,.82),(5.5,1.35),(5.,1.0)]}
 # Hair 4 and 5.3 Beni; mixed hair Feingold; Hg0 urine/blood Colombia;
 # MeHg blood 7.4 Peru native-community median (transport assumption).
 # All other anchors and exposure slopes are [SUPUESTO_SIMULACION_MVP].
 segment=r.integers(1,4,n); h=50.; L=30.*segment
 # mean historical decay over proximal segment, not decay of deposited hair
 past=np.maximum(days-L,0); elapsed=np.minimum(days,L)
 hair_k=(L-elapsed + h/np.log(2)*(2**(-past/h)-2**(-days/h)))/L
 diet=np.log1p(edi*4); occ=np.log1p(hours)*(1+.35*closed-.30*retort)+.6*i
 scores=np.column_stack([.50*diet+np.log(hair_k),.40*occ-np.log(2)*days/60,.30*diet+.25*occ-np.log(2)*days/50])
 true=biomarker_layer(r,n,g,scores,anchors)
 # Stress-test subgroup within Hg0/Hg2, not empirical prevalence; adds upper-tail coverage.
 stress=(v|i)&(r.random(n)<.12); true[stress,1]*=12; true[stress,2]*=2
 hair,urine,blood=true.T
 # Baselines and slopes are explicit simulation assumptions. Calibrate intercepts
 # to expected baseline prevalence over simulated controls (not published prevalence).
 base=np.array([.05,.025,.015,.04,.02,.006,.025,.004,.004,.01,.012,.06,.025,.04,.05,.03,.018,.025,.003,.012,.08,.10,.10,.008,.009,.02,.05,.025,.04,.07])
 beta=np.array([.40,.45,.45,.45,.45,.65,.65,.5,.5,.2,.35,.35,.35,.35,.4,.4,.65,.5,.25,.25,.45,.45,.55,.60,.75,.65,.65,.80,.55,.55])
 # Distinct phenotype drivers; renal symptoms not equated to laboratory CKD.
 domains=['oral','oral','oral','oral','oral','oral','oral','oral','oral','renal','renal','renal','renal','renal','resp','resp','visual','resp','visual','renal','eret','eret','eret','visual','visual','visual','visual','motor','resp','resp']
 dose={'oral':np.log1p(urine),'renal':np.log1p(urine),'resp':np.log1p(occ*2**(-days/10)),'visual':np.log1p(hair),'eret':np.log1p(urine),'motor':np.log1p(hair)+.5*np.log1p(urine)}
 # FALLBACK: no standardized symptom-specific delta_y published; proxy values only.
 beta=np.array([effect_to_logit(x) for x in beta])
 symptoms,intercept,shared,individual=clinical_layer(r,n,control,dose,age,base,beta,domains)
 exposed=bern(np.where(control,.12,.91)); mining=bern(np.where(v|i,.85,.35)); family=bern(np.where(v|i,.65,.32)); occupation=np.where(child,'Estudiante',np.where(v & (burn>0),'Mineria',r.choice(['Agricultura','Comercio','Hogar','Pesca','Otros'],n)))
 d=dict(zip(PRE[:18],[notif,dep,mun,loc,np.char.add('CS_',loc),exposed,np.where(rural,'Búsqueda activa','Vigilancia pasiva'),np.where(rural,'Otro','Consulta Externa'),age,np.where(female,'F','M'),weight,occupation,mun,loc,np.where(fertile,preg.astype(float),np.nan),np.where(fertile,lact.astype(float),np.nan),np.where(female&(age>=15),r.poisson(2,n),np.nan),np.where(female&(age>=15),bern(.09),np.nan)]))
 d.update(dict(zip(PRE[18:41],[exposure,years,np.where(v,'Mineria',np.where(i,'Manipulacion',np.where(fish,'Alimentacion','No identificado'))),occupation,hours,burn,np.where(burn>0,closed,np.nan),np.where(burn>0,retort,np.nan),bern(np.where(v,.87,.09)),bern(np.where(v|i,.65,.07)),bern(np.where(fish,.92,.12)),np.zeros(n,int),bern(np.where(v|i,.75,.06)),bern(np.where(i,.45,.04)),bern(np.where(m,.85,.25)),mining,fish,freq,(pred>0).astype(int),pred,portion,family,np.where(family,r.choice(['Padre','Madre','Pareja','Otro'],n),None)])))
 for j,c in enumerate(CLIN): d[c]=symptoms[:,j].astype(float)
 onset=notif-pd.to_timedelta(r.integers(0,30,n),unit='D'); d[PRE[-1]]=onset.where(symptoms.any(axis=1))
 df=pd.DataFrame(d,columns=PRE)
 # MAR: recording differs by capture context; MNAR: sensitive practices and symptom reporting.
 for c in ['EXT_10b_peso_corporal_kg','EXT_32d_tamano_porcion_gramos','antecedente_exposicion_anterior_anos']:
  df.loc[perturbation_layer(r,~rural,.3),c]=np.nan
 df.loc[(burn>0)&(perturbation_layer(r,~rural,.4,closed)),'EXT_27c_quema_espacio_cerrado_o_vivienda']=np.nan
 for j,c in enumerate(CLIN): df.loc[perturbation_layer(r,~rural,(j+35)/82,symptoms[:,j]),c]=np.nan
 # Sample availability depends on exposure context, access and unobserved burden (MNAR).
 prob=np.column_stack([.35+.35*m,.35+.35*(v|i),.35+.12*(v|i|m)])-.13*rural[:,None]+.08*(true>np.array([5,50,20])); available=r.random((n,3))<prob
 observed=np.where(available,np.round(true*r.lognormal(0,.12,(n,3)),2),np.nan)
 eligible=np.flatnonzero(available.any(axis=1)); count=round(.08*len(eligible)); flags=np.zeros(n,int); kinds=np.full(n,'ninguna',object)
 # Hair contamination: mining environment, low symptom count, independent of dietary dose conditional on eligibility.
 candidates=np.flatnonzero(available[:,0]&mining.astype(bool)&(symptoms.sum(axis=1)<=2))
 contam=r.choice(candidates,min(count//2,len(candidates)),replace=False)
 observed[contam,0]+=r.lognormal(np.log(30),.65,len(contam)); flags[contam]=1; kinds[contam]='contaminacion_externa_cabello'
 scale=r.choice(np.setdiff1d(eligible,contam),count-len(contam),replace=False)
 for k in scale:
  j=int(r.choice(np.flatnonzero(available[k]))); factor=int(r.choice([100,1000])); observed[k,j]*=factor; flags[k]=1; kinds[k]=f'error_escala_x{factor}'
 observed=np.round(observed,2); primary=np.argmax(available,axis=1); has=available.any(axis=1); sample=np.array(['Cabello','Orina','Sangre'])[primary]; unit=np.array(['ug/g','ug/g Cr','ug/L'])[primary]; taken=notif+pd.to_timedelta(r.integers(0,8,n),unit='D'); sent=taken+pd.to_timedelta(r.integers(0,7,n),unit='D')
 for c,val in zip(LAB,[np.where(has,sample,None),taken.where(has),sent.where(has),np.where(has,observed[np.arange(n),primary],np.nan),np.where(has,unit,None),np.where(available[:,0],segment,np.nan),*observed.T]): df[c]=val
 # Clean synthetic reference labels only where corresponding test exists; corruption never becomes truth.
 for c,j,t in zip(Y[1:5],[0,0,1,1],[3,5,20,50]): df[c]=pd.array((true[:,j]>=t).astype(int),dtype='Int8')
 # Guide operational proxy: probable + both blood and urine above references; blood 20 chosen conservatively.
 # Not official adjudication; absence of tests never means negative.
 probable=(exposed.astype(bool)|mining.astype(bool))&(df[CLIN].fillna(0).to_numpy()==1).any(axis=1); both=available[:,1]&available[:,2]; positive=(true[:,1]>50)&(true[:,2]>20)
 df[Y[0]]=np.where(probable,np.where(both&positive,'Confirmado_simulado','Probable_simulado'),'No_clasificado_simulado'); df[Y[-1]]=flags
 df=df[PRE+LAB+Y]; out.mkdir(parents=True,exist_ok=True)
 # 71 numbered official fields: collapse multi-select routes/types; restore nine omitted administrative fields.
 official=df[PRE+[c for c in LAB if not c.startswith('lab_')]].copy()
 for prefix, cols in [('via_exposicion',['via_respiratoria','via_dermica','via_oral','via_desconocida']),('tipo_exposicion',['tipo_ocupacional','tipo_accidental','tipo_ambiental'])]:
  official[prefix]=official[cols].apply(lambda row:';'.join(c for c in cols if row[c]==1) or 'No especificado',axis=1); official.drop(columns=cols,inplace=True)
 for c in ['nombre_apellido','ci','telefono','nombre_padres_apoderados','residencia_anterior','nombre_apellido_notificador','cargo_notificador','observaciones','firma']:
  official[c]=pd.NA
 official['nombre_apellido']=[f'SINTETICO_{k:04d}' for k in range(n)]
 official['residencia_anterior']=df['residencia_actual']; official['nombre_apellido_notificador']='NOTIFICADOR_SINTETICO'; official['cargo_notificador']='Personal de salud'
 assert list(official.columns)==SCHEMA
 assert official.shape==(n,82) and sum(c.startswith('EXT_') for c in official)==11

 # One fixed split shared by all matrices. Row index is join key in separate manifest, never a feature.
 perm=r.permutation(n); split=np.full(n,'train',object); split[perm[1050:1275]]='validation'; split[perm[1275:]]='test'
 audit=pd.DataFrame({'row_id':np.arange(n),'split':split,'escenario_latente':pd.Series(g).map(COHORT_LABELS),'talla_cm':height,'imc':bmi,'EXT_anomalia_tipo':kinds,'hair_available':available[:,0],'urine_available':available[:,1],'blood_available':available[:,2],'anomalia_tipo':kinds,'hair_clean':true[:,0],'urine_clean':true[:,1],'blood_clean':true[:,2],'edi_latente':edi,'vulnerable':child|fertile|preg|lact,'stress_tail_assumed':stress})
 files={'ficha_mercurio_bolivia_v2':official,'pipeline_87_campos':df,'X_M1':df[FEATURES],'X_M3A':df[FEATURES],'X_M3B':df[FEATURES+[c for c in LAB if c.startswith('lab_')]],'Y':df[Y], 'Y_observabilidad':pd.DataFrame(dict(zip(Y[1:5],[available[:,0],available[:,0],available[:,1],available[:,1]]))),'auditoria_latente_NO_ENTRENAR':audit}
 # Export the same source identity with each record before serialization.
 row_id=official['nombre_apellido'].str.removeprefix('SINTETICO_').astype(int)
 for name,frame in files.items():
  if keyed:
   if name=='ficha_mercurio_bolivia_v2':
    frame=frame.assign(**{c: df[c] for c in LAB if c.startswith('lab_')})
   if name=='auditoria_latente_NO_ENTRENAR':
    frame=frame.assign(row_id=row_id,flag_anomalia_real=flags)
   else:
    frame=frame.assign(row_id=row_id)[['row_id',*frame.columns]]
  frame.to_csv(out/(name+'.csv'),index=False)
 try: official.to_parquet(out/'ficha_mercurio_bolivia_v2.parquet',index=False)
 except ImportError: warnings.warn('Parquet no generado: instalar pyarrow o fastparquet y volver a ejecutar.')
 assert df.shape==(1500,len(PRE)+len(LAB)+len(Y)) and df.columns.is_unique
 assert not df[Y].isna().any().any()
 assert not set(FEATURES)&set(LAB+Y) and not set(files['X_M3B'])&set(Y)
 assert (pred<=freq).all() and (years<=age).all() and (sent>=taken).all() and (exposure<=notif).all()
 assert (df[Y[2]].dropna()<=df.loc[df[Y[2]].notna(),Y[1]]).all(); assert (df[Y[4]].dropna()<=df.loc[df[Y[4]].notna(),Y[3]]).all()
 assert not (flags.astype(bool)&~has).any(); assert np.all(observed[available]>=0)
 for c in Y[1:5]:
  for s in ['train','validation','test']: assert df.loc[split==s,c].dropna().nunique()==2,(c,s)
 report={'shape':list(official.shape),'pipeline_shape':list(df.shape),'empirical_checks':{cohort:{name:{'anchor_median':float(params[j][0]),'sim_median':float(np.median(true[g==cohort,j])),'sim_p75':float(np.quantile(true[g==cohort,j],.75)),'sim_p95':float(np.quantile(true[g==cohort,j],.95))} for j,name in enumerate(['hair','urine','blood'])} for cohort,params in anchors.items()},'clinical_beta0':dict(zip(CLIN,map(float,intercept))),'clinical_beta1_assumed':dict(zip(CLIN,map(float,beta))),'baseline_assumed':dict(zip(CLIN,map(float,base))),'control_urine_censored_model_median':float(np.exp(cu_mu)),'cohorts':pd.Series(g).value_counts().to_dict(),'missing_total':float(official.isna().mean().mean()),'missing_by_column':df.isna().mean().to_dict(),'targets':{c:{'n_observed':int(df[c].count()),'positive_rate':float(df[c].mean())} for c in Y[1:]},'classification':df[Y[0]].value_counts().to_dict(),'anomalies':int(flags.sum()),'measured_rows':int(has.sum()),'hair_median_dietary_clean':float(np.median(true[g=='MeHg',0])),'children':int(child.sum()),'fertile':int(fertile.sum()),'pregnant':int(preg.sum()),'lactating':int(lact.sum()),'checks':'PASS: schema, temporal order, nested targets, feature exclusion, class support, exposure consistency'}
 validation=validate_fidelity(official,df,true,g,anchors,symptoms,shared,individual,base,beta,z,files,available,flags)
 (out/'validation_report.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False),encoding='utf8')
 report['target_semantics']='All Y biomarker thresholds are synthetic oracle labels, not measured diagnoses. Use Y_observabilidad for realistic supervised evaluation.'
 (out/'sanity_checks.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 sources={'control_blood':'ATSDR 2024 table 5-25, https://www.ncbi.nlm.nih.gov/books/NBK611006/table/ch5.tab25/', 'control_urine':'ATSDR 2024 table 5-33; censored median extrapolation', 'beni_hair':'PMID 19004394','fish':'DOI 10.1016/j.jfca.2025.108840','peru':'PMID 22926732; PMID 31627842','colombia':'PMID 27449026; DOI 10.1177/0748233716659031','clinical':'PMID 9756677; PMID 10787135; directional only','missing':'DOI 10.1093/biomet/63.3.581; mechanism only','contamination':'PMID 7509168; mechanism only','kinetics':'DOI 10.1080/10408440600845619','guide':'Guía 537 Cuadro 3; urine unit ug/g not explicitly Cr; operational proxy'}
 metadata={'seed':SEED,'versions':{'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},'scenario_probabilities_FALLBACK':dict(zip(COHORT_LABELS.values(),PROBS)),'sources':sources,'anchors_median_sigma':anchors,'schema':SCHEMA,'sigma_u_shared':.45,'sigma_u_individual':.30,'traduccion_efectos':{c:{'delta_y_empirico':None,'delta_y_proxy':float(b),'beta_1':float(b),'fuente':'FALLBACK: no comparable symptom-specific effect; PMID 9756677 / 10787135 directional only'} for c,b in zip(CLIN,beta)},'justificacion_perturbaciones':{'MAR_MNAR':'FALLBACK: logit=-3+0.8*consulta+0.6*position+0.55*hidden; Rubin defines mechanism, not local rates','anomalies':'FALLBACK 8%; PMID 7509168 supports external contamination mechanism only','scale':'FALLBACK x100/x1000'},'parameter_policy':'All constants not specifically anchored are FALLBACK design assumptions, not literature estimates; see script equations.','validation':validation,'parquet_generated':(out/'ficha_mercurio_bolivia_v2.parquet').exists(),'sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.suffix in ['.csv','.parquet','.py','.json'] and f.name!='metadata.json'}}
 (out/'metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf8')
 print(json.dumps({'shape':list(official.shape),'validation':validation['summary'],'parquet':metadata['parquet_generated']},indent=2))

def validate_fidelity(official,df,true,g,anchors,symptoms,shared,individual,base,beta,z,files,available,flags):
 """Model-reference KS (not independent empirical KS); Wilson CI; Spearman; structural assertions."""
 assert official.shape==(N,82) and list(official)==SCHEMA and not df[Y].isna().any().any()
 assert not set(files['X_M1'])&set(LAB+Y) and not set(files['X_M3A'])&set(LAB+Y) and not set(files['X_M3B'])&set(Y)
 continuous={}
 for cohort,params in anchors.items():
  for j,(med,sd) in enumerate(params):
   values=true[g==cohort,j]; ks=kstest(np.log(values),'norm',args=(np.log(med),sd))
   continuous[f'{COHORT_LABELS[cohort]}:{j}']={'reference_model_median':float(med),'generated_median':float(np.median(values)),'median_difference':float(np.median(values)-med),'KS_D_model':float(ks.statistic),'KS_p_model_descriptive':float(ks.pvalue),'empirical_KS':None}
 binary={}
 for j,c in enumerate(CLIN):
  a=symptoms[g=='control',j]; ci=binomtest(int(a.sum()),len(a)).proportion_ci(method='wilson')
  binary[c]={'prevalence':float(a.mean()),'wilson95':[float(ci.low),float(ci.high)],'baseline_assumed':float(base[j]),'published_comparable':None}
 rho=np.array([[spearmanr(symptoms[:,j],true[:,k]).statistic for k in range(3)] for j in range(30)])
 maxrho=float(np.nanmax(abs(rho))); assert maxrho<.95
 # Test exogenous noise only against upstream observed numeric covariates, not descendants.
 cov=np.column_stack([z['age'],z['female'],z['weight'],z['height'],z['preg'],z['lact']])
 rc=np.corrcoef(np.column_stack([cov,shared,individual]),rowvar=False)[:cov.shape[1],cov.shape[1]:]
 maxnoise=float(np.max(np.abs(rc)))
 return {'summary':{'structural_assertions':'PASS','max_abs_symptom_biomarker_spearman':maxrho,'max_abs_noise_upstream_pearson':maxnoise,'noise_threshold_0_05_pass':maxnoise<.05,'empirical_validation':'NOT ESTABLISHED','targets_null':int(df[Y].isna().sum().sum()),'anomalies':int(flags.sum()),'measured':int(available.any(axis=1).sum())},'continuous':continuous,'binary_controls':binary,'spearman':{c:dict(zip(['hair','urine','blood'],map(float,row))) for c,row in zip(CLIN,rho)},'limitations':['KS against specified theoretical distribution, not published raw observations; p-values descriptive after calibration','No comparable published symptom prevalences or Spearman coefficients; cannot validate empirically','Random effects influence symptoms by design; correlation checks only upstream covariates, not proof of independence','All Y complete by oracle labeling; missing laboratory is not negative','EXT exposure inputs causally precede symptoms via biomarkers; no observed EXT or Y passed to clinical_layer']}
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=Path('.')); p.add_argument('--verify-reproducibility',action='store_true'); p.add_argument('--keyed',action='store_true'); args=p.parse_args(); generate(args.out,keyed=args.keyed)
 if args.verify_reproducibility:
  with tempfile.TemporaryDirectory() as tmp:
   generate(Path(tmp),keyed=args.keyed); names=['ficha_mercurio_bolivia_v2.csv','Y.csv','X_M1.csv','X_M3A.csv','X_M3B.csv','auditoria_latente_NO_ENTRENAR.csv','Y_observabilidad.csv']
   if (args.out/'ficha_mercurio_bolivia_v2.parquet').exists(): names.append('ficha_mercurio_bolivia_v2.parquet')
   for name in names: assert (args.out/name).read_bytes()==(Path(tmp)/name).read_bytes(),name
   meta=args.out/'metadata.json'; data=json.loads(meta.read_text()); data['reproducibility']={'bitwise_equal':True,'files':names}; meta.write_text(json.dumps(data,indent=2,ensure_ascii=False)); print('REPRODUCIBILITY PASS')
