"""Independent Python byte/hash oracle. All records are synthetic, never Admin approvals."""
from pathlib import Path
import json, hashlib, copy

ROOT = Path(__file__).resolve().parents[1] / 'fixtures' / 'atlas-delivery'
ROOT.mkdir(parents=True, exist_ok=True)
def encode(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def digest(value): return hashlib.sha256(encode(value).encode()).hexdigest()
def uuid(i): return f'01a00000-0000-7000-8000-{i:012d}'
def signed(value): return dict(value, sha256=digest(value))
def rational(n, d=1): return dict(numerator=str(n), denominator=str(d))
def save(name, value): (ROOT/name).write_text(encode(value), encoding='utf-8')

dimension=dict(id=uuid(1),code='mass',names={'en':'TEST mass'},vector=[0,1,0,0,0,0,0])
policy={k:'TEST ONLY' for k in ['aliases','context','exact_arithmetic','exactness_scope','expressions','release','rule','temperature']}
policy.update(conversion_request=['snapshot_sha256','quantity_kind_id','from_unit_id','to_unit_id','value_num','value_den'],deferred=[],out_of_scope=['TEST ONLY'])
reference_bytes={'TEST_ONLY':'synthetic scientific reference'}
ref_hash=digest(reference_bytes)

def make_unit(release_id, version, source_id='TEST', unit_code='kg'):
 unit=dict(id=uuid(3),code=unit_code,symbol=unit_code,names={'en':'TEST unit'},dimension_id=uuid(1),dimension_code='mass',definition_type='atomic',exactness='exact',scale_num=1,scale_den=1,expression_factor_num=1,expression_factor_den=1,source_id=source_id,evidence='TEST ONLY')
 scientific=dict(reference_sha256=ref_hash,reference_kind_id=uuid(2),quantity_role='ratio',context_fields=[],physical_dimension=dimension,unit_definition=unit,terms=[])
 base=dict(release_id=release_id,unit_type_id=uuid(3),unit_dimension_id=uuid(2),unit_code=unit_code,unit_symbol=unit_code,dimension_code='mass',transform_kind='ratio',is_base=True,scale=rational(1),offset=rational(0),scientific=scientific)
 entry=dict(base,id=uuid(4),quantity_kind_id=uuid(2),sha256=digest(base)); del entry['release_id']
 return dict(schema_version='unit-catalog-release/v2',release=dict(id=release_id,version=version),definitions=[entry],conversions=[],reference=dict(version='TEST-ref-v1',sha256=ref_hash,dimension_axes=['length','mass','time','electric_current','temperature','amount','luminous_intensity'],physical_dimensions=[dimension],aliases=[],quantity_kind_mappings=[dict(quantity_kind_id=uuid(2),reference_kind_id=uuid(2),code='mass')],policy=policy))

unit=make_unit(uuid(5),'TEST-base-v1')
geography=dict(schema_version='netzero-geography-snapshot/v1',owner='NetZeroAdmin',countries=[dict(id=uuid(10),iso2='TR',iso3='TUR',numeric_code='792',active=True,deleted=False,usable=True,names=[])],provinces=[],districts=[])
currency=dict(schema_version='netzero-currency-snapshot/v1',owner='NetZeroAdmin',policy=dict(fx_conversion=False,scientific_dimension=False,symbols_are_aliases=False),currencies=[signed(dict(id=uuid(11),code='EUR',name='TEST Euro',symbol='€',active=True,deleted=False,usable=True))])
uses=dict(schema_version='netzero-intended-use-snapshot/v1',owner='NetZeroAdmin',policy=dict(applicability_inferred=False,human_review_required=True,labels_are_aliases=False),uses=[signed(dict(canonical_id=k,active=True,compatibility='human_review_required',description='TEST ONLY',names={'en':'TEST '+k,'tr':'TEST '+k})) for k in ['corporate_carbon_footprint','life_cycle_assessment','product_carbon_footprint']])
kinds=['protocol','scope','segment','category','consumption_type','material']
ids={k:uuid(20+i) for i,k in enumerate(kinds)}
parents={'segment':['protocol:'+ids['protocol'],'scope:'+ids['scope']],'category':['segment:'+ids['segment']],'material':['consumption_type:'+ids['consumption_type']]}
nodes=[signed(dict(id=ids[k],canonical_id=k+':'+ids[k],kind=k,parents=parents.get(k,[]),names=[],active=True,deleted=False,main=None,sort_order=1)) for k in kinds]
taxonomy=dict(schema_version='netzero-taxonomy-snapshot/v1',owner='NetZeroAdmin',policy=uses['policy'],nodes=nodes,category_consumption_links=[signed(dict(id=uuid(30),category_id=ids['category'],consumption_type_id=ids['consumption_type'],deleted=False,sort_order=1))])
catalogs=dict(unit=unit,geography=geography,currency=currency,taxonomy=taxonomy,intended_use=uses)
save('catalogs.json',catalogs)

def unit_ref(value):
 d=value['definitions'][0]
 return dict(catalog_version=value['release']['version'],catalog_sha256=digest(value),definition_id=d['id'],definition_sha256=d['sha256'],quantity_kind_id=d['quantity_kind_id'],unit_code=d['unit_code'])
base_ref=unit_ref(unit)
transform=dict(direction='target = source * scale + offset',scale=rational(1),offset=rational(0))
currency_ref=dict(catalog_version='sha256:'+digest(currency),catalog_sha256=digest(currency),currency_id=uuid(11),entry_sha256=currency['currencies'][0]['sha256'],code='EUR')
proposals={
 'alias':dict(type='alias',target=base_ref),
 'exact_conversion':dict(type='exact_conversion',exactness='definitional',**{'from':base_ref,'to':base_ref},transform=transform),
 'context_relation':dict(type='context_relation',relation='calorific_value',explanation='TEST ONLY, non executable',required_parameters=['calorific_value'],context_document=None),
 'monetary_measure':dict(type='monetary_measure',context_document=None,currency_code_proposal='EUR',currency_ref=currency_ref,reference_amount=rational(1000)),
 'new_unit':dict(type='new_unit',code='test_mass',symbol='test-mass',names={'en':'TEST mass','tr':'TEST kütle'},quantity_role='ratio',dimension_vector=[0,1,0,0,0,0,0],exactness='definitional',target=base_ref,transform=transform),
 'new_quantity_kind':dict(type='new_quantity_kind',local_key='test_mass',names={'en':'TEST mass kind','tr':'TEST kütle türü'},quantity_role='ratio',dimension_vector=[0,1,0,0,0,0,0],terms=[dict(definition_ref=base_ref,exponent=1)]),
}
cases={}
for kind,proposed in proposals.items():
 raw='TEST ONLY raw source\n'
 raw_pin=dict(asset_key='fixtures/test-source',sha256=hashlib.sha256(raw.encode()).hexdigest(),size_bytes=len(raw.encode()))
 source=dict(code='TEST',dataset='synthetic-only',release='TEST-release-v1',raw=raw_pin)
 fields={'unit':'TEST mass','value':'2.00000000000000000001'}
 proposal=dict(schema_version='netzero-source-proposal/v1',candidate_ref=None,source=source,proposal_key='TEST/'+kind,revision=1,previous_sha256=None,producer=dict(owner='NetZeroAtlas',normalizer_version='TEST/1'),observation=dict(claim_origin='normalizer_inference',field='unit',original_fields=fields,original_fields_sha256=digest(fields),raw_label='TEST mass',source_record_id='TEST-row',source_record_number=1),evidence=[dict(locator='TEST row 1',relationship='source_raw',sha256=raw_pin['sha256'])],proposal=proposed)
 identity=digest(dict(source_code=source['code'],dataset=source['dataset'],release=source['release'],raw_sha256=raw_pin['sha256'],proposal_key=proposal['proposal_key']))
 receipt=dict(schema_version='netzero-source-proposal-central-receipt/v1',identity_sha256=identity,revision=1,proposal_sha256=digest(proposal),canonical_write_allowed=False,publish_allowed=False)
 resolution=dict(schema_version='admin-source-resolution/1',source_proposal_revision_id=uuid(41),proposal_sha256=digest(proposal),receipt_sha256=digest(receipt),version=1,previous_resolution_id=None,form=dict(unit_catalog_sha256=digest(unit)),validation=dict(ruleset_sha256='a'*64,errors=[],proposal=proposed))
 decision=dict(source_proposal_resolution_id=uuid(42),supersedes_decision_id=None,decision='approve',evidence_checked=True,resolution_sha256=digest(resolution),ruleset_sha256='a'*64,publish_allowed=False,canonical_write_allowed=False)
 pin=dict(family_id=uuid(40),identity_sha256=identity,source=source,proposal_key=proposal['proposal_key'],revision_id=uuid(41),revision=1,proposal_sha256=digest(proposal),receipt_sha256=digest(receipt),resolution_id=uuid(42),resolution_version=1,resolution_sha256=digest(resolution),previous_resolution_id=None,decision_id=uuid(43),decision_sha256=digest(decision),supersedes_decision_id=None,ruleset_sha256='a'*64,proposal_type=kind,status='approved_at_lookup',published_target=None)
 artifacts={'source/raw':raw,'source/proposal.json':encode(proposal),'source/receipt.json':encode(receipt),'resolution/payload.json':encode(resolution),'resolution/decision.json':encode(decision)}
 target=None
 if kind in ['new_unit','new_quantity_kind']:
  target=make_unit(uuid(50),'TEST-target-v2','resolution:'+uuid(42),'test_mass')
  pin['published_target']=unit_ref(target)
  provenance=dict(resolution_sha256=pin['resolution_sha256'],decision_sha256=pin['decision_sha256'],base_catalog_sha256=digest(unit),unit_catalog_release_id=uuid(50),reference_sha256=ref_hash)
  artifacts['resolution/scientific-provenance.json']=encode(provenance)
  artifacts['resolution/scientific-reference.json']=encode(reference_bytes)
 cases[kind]=dict(pin=pin,artifacts=artifacts,target=target)
save('resolutions.json',cases)
save('oracle.json',dict(unit_sha256=digest(unit),unit_definition_sha256=unit['definitions'][0]['sha256'],currency_sha256=digest(currency),source_decimal=fields['value']))
