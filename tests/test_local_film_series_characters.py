import json,tempfile,unittest
from pathlib import Path
from local_film import characters
from local_film.pipeline import JobError
VOICE='en_US-amy-medium.onnx'

def touch(path):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x89PNG fake');return path

def make_character(root,slug,**overrides):
 character={'id':slug,'name':'Alice','description':'A composed radio operator who trusts instruments more than rumors.',
  'appearance':'Short grey hair, olive skin, always a navy wool jacket.','voice_model':VOICE,'voice_sample':'audition-amy.wav',
  'portrait':'portrait.png','ref_images':['portrait.png','refs/turn-01.png']}
 character.update(overrides);base=Path(root)/'characters'/slug
 touch(base/character['voice_sample']);touch(base/character['portrait']);touch(base/'refs/turn-01.png')
 for ref in character['ref_images'][1:]:touch(base/ref) if ref!='refs/turn-01.png' else None
 (base/'character.json').write_text(json.dumps(character),encoding='utf8');return character

def make_show(root,cast=('alice',),**overrides):
 show={'id':'polar-night','title':'Polar Night','logline':'Two radio operators decode a signal that should not exist.',
  'brief':'Cold blue realism at a polar listening post.','style':'Cold blue-white cinematic realism, 35mm grain.',
  'arc_summary':'Episode 1 ends at the ice shelf.','width':1280,'height':720,'fps':24,'characters':list(cast)}
 show.update(overrides);base=Path(root)/'polar-night';base.mkdir(parents=True,exist_ok=True)
 (base/'show.json').write_text(json.dumps(show),encoding='utf8');return show

def shot(number=1,characters_=('alice',),dialogue=None,**overrides):
 value={'id':f'shot-{number:02d}','scene':'inside the radio hut at night','setting':'cluttered desk lit by one amber lamp',
  'action':'Alice leans closer to the receiver.','continuation_action':'She holds the headphones to her ear.',
  'prompt':'Medium shot of Alice at the desk.','characters':list(characters_),'speakers':list(characters_)[:1],
  'dialogue':dialogue if dialogue is not None else [{'character':characters_[0],'text':'Do you hear that?'}]}
 value.update(overrides);return value

def make_episode(root,shots=None,**overrides):
 episode={'id':'01-first-light','number':1,'title':'First Light','target_seconds':90,
  'shots':shots if shots is not None else [shot()],'synopsis':'The first anomaly.','ending_state':'Alice steps out onto the ice.','next_hook':'The signal answers.'}
 episode.update(overrides);base=Path(root)/'polar-night/episodes/01-first-light';base.mkdir(parents=True,exist_ok=True)
 (base/'episode.json').write_text(json.dumps(episode),encoding='utf8');return episode

class SeriesCharacterRegistryTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name)
  make_character(self.root,'alice');make_character(self.root,'bob',name='Bob',description='A young glaciologist who maps the ice on foot every clear morning.');make_show(self.root,cast=('alice','bob'))
 def tearDown(self):self._tmp.cleanup()
 def test_valid_tree_loads(self):
  character=characters.load_character(self.root,'alice')
  self.assertEqual(character['id'],'alice');self.assertTrue(Path(character['_dir']).is_dir())
  show=characters.load_show(self.root,'polar-night')
  self.assertEqual(show['characters'],['alice','bob']);self.assertEqual(show['width'],1280);self.assertEqual(show['fps'],24)
  cast=characters.load_cast(self.root,show);self.assertEqual(set(cast),{'alice','bob'})
 def test_episode_loads_by_id_and_number(self):
  make_episode(self.root,shots=[shot(),shot(2,characters_=('bob',))])
  by_id=characters.load_episode(self.root,'polar-night','01-first-light')
  by_number=characters.load_episode(self.root,'polar-night',1)
  self.assertEqual(by_id['shots'][1]['characters'],['bob']);self.assertEqual(by_id['id'],by_number['id'])
  self.assertEqual(by_id['_dir'],str(self.root/'polar-night/episodes/01-first-light'));self.assertEqual(by_id['_show'],'polar-night')
 def test_empty_dialogue_becomes_cast_narration(self):
  make_episode(self.root,shots=[shot(dialogue=[])])
  episode=characters.load_episode(self.root,'polar-night',1)
  self.assertEqual(episode['shots'][0]['dialogue'],[{'character':'alice','text':'<narration>'}])
 def test_automatic_and_fixed_target_seconds(self):
  make_episode(self.root,target_seconds=0);self.assertEqual(characters.load_episode(self.root,'polar-night',1)['target_seconds'],0)
  make_episode(self.root,target_seconds=45);self.assertEqual(characters.load_episode(self.root,'polar-night',1)['target_seconds'],45)
 def test_character_id_must_equal_folder(self):
  character=make_character(self.root,'alice');character['id']='someone-else'
  (self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'must equal its folder slug'):characters.load_character(self.root,'alice')
 def test_short_description_rejected(self):
  character=make_character(self.root,'alice',description='too short');(self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'at least 20 characters'):characters.load_character(self.root,'alice')
 def test_voice_model_must_be_bare_existing_filename(self):
  for bad in ('../en_US-amy-medium.onnx','models/en_US-amy-medium.onnx','en_US-nobody-medium.onnx'):
   character=make_character(self.root,'alice',voice_model=bad);(self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
   with self.assertRaises(JobError):characters.load_character(self.root,'alice')
 def test_voice_sample_must_exist(self):
  make_character(self.root,'alice');(self.root/'characters/alice/audition-amy.wav').unlink()
  with self.assertRaisesRegex(JobError,'voice_sample does not exist'):characters.load_character(self.root,'alice')
 def test_portrait_must_be_first_reference(self):
  character=make_character(self.root,'alice');character['ref_images']=['refs/turn-01.png','portrait.png']
  (self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'master portrait first'):characters.load_character(self.root,'alice')
 def test_reference_count_bounds(self):
  character=make_character(self.root,'alice');character['ref_images']=['portrait.png']
  (self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'between 2 and 9'):characters.load_character(self.root,'alice')
  many=['portrait.png']+['refs/turn-%02d.png'%i for i in range(1,10)]
  character['ref_images']=many
  for ref in many[1:]:touch(self.root/'characters/alice'/ref)
  (self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'between 2 and 9'):characters.load_character(self.root,'alice')
 def test_reference_escapes_folder(self):
  character=make_character(self.root,'alice');character['ref_images']=['portrait.png','../../outside.png']
  (self.root/'characters/alice/character.json').write_text(json.dumps(character),encoding='utf8')
  with self.assertRaisesRegex(JobError,'escapes the character folder'):characters.load_character(self.root,'alice')
 def test_show_dimension_and_cast_rules(self):
  make_show(self.root,width=1281);
  with self.assertRaisesRegex(JobError,'even'):characters.load_show(self.root,'polar-night')
  make_show(self.root,fps=25)
  with self.assertRaisesRegex(JobError,'fps must be 24'):characters.load_show(self.root,'polar-night')
  make_show(self.root,cast=[])
  with self.assertRaisesRegex(JobError,'at least one character'):characters.load_show(self.root,'polar-night')
 def test_show_requires_arc_summary_text(self):
  make_show(self.root,arc_summary='  ')
  with self.assertRaisesRegex(JobError,'arc_summary is required'):characters.load_show(self.root,'polar-night')
 def test_show_cast_character_must_exist(self):
  make_show(self.root,cast=('alice','ghost'))
  with self.assertRaises(JobError):characters.load_show(self.root,'polar-night')
 def test_episode_id_must_equal_folder(self):
  make_episode(self.root);path=self.root/'polar-night/episodes/01-first-light/episode.json'
  episode=json.loads(path.read_text(encoding='utf8'));episode['id']='01-something-else';path.write_text(json.dumps(episode),encoding='utf8')
  with self.assertRaisesRegex(JobError,'must equal its folder name'):characters.load_episode(self.root,'polar-night','01-first-light')
 def test_target_seconds_bounds(self):
  make_episode(self.root,target_seconds=15)
  with self.assertRaisesRegex(JobError,'automatic'):characters.load_episode(self.root,'polar-night','01-first-light')
 def test_shot_bounds_and_membership(self):
  make_episode(self.root,shots=[shot(1,characters_=('carl',))])
  with self.assertRaisesRegex(JobError,'outside the show cast'):characters.load_episode(self.root,'polar-night',1)
  make_episode(self.root,shots=[shot(speakers=('bob',))])
  with self.assertRaisesRegex(JobError,'subset of the shot characters'):characters.load_episode(self.root,'polar-night',1)
  make_episode(self.root,shots=[shot(i+1)for i in range(13)])
  with self.assertRaisesRegex(JobError,'1 to 12 shots'):characters.load_episode(self.root,'polar-night',1)
  make_episode(self.root,shots=[shot(id='take-01')])
  with self.assertRaisesRegex(JobError,'shot-01 through shot-99'):characters.load_episode(self.root,'polar-night',1)
  make_episode(self.root,shots=[shot(),shot()])
  with self.assertRaisesRegex(JobError,'unique'):characters.load_episode(self.root,'polar-night',1)

if __name__=='__main__':unittest.main()
