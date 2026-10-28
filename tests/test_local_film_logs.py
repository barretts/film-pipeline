import tempfile,unittest
from pathlib import Path
from local_film.logs import log_tail

class LogTailTests(unittest.TestCase):
 def test_terminal_codes_and_repeated_progress_are_cleaned(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'process.log'
   path.write_bytes(b'\x1b[32m[INFO]\x1b[0m Loading\r\n 25%|xx| 1/4 [00:01]\r 50%|xxxx| 2/4 [00:02]\r\n\x1b[33m[WARNING]\x1b[0m Low memory\n[ERROR] Failure\n')
   self.assertEqual(log_tail(path),['[INFO] Loading','50%|xxxx| 2/4 [00:02]','[WARNING] Low memory','[ERROR] Failure'])
 def test_missing_and_bounded_logs(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'process.log';self.assertEqual(log_tail(path),[])
   path.write_text('\n'.join('Message '+str(i) for i in range(1000)),encoding='utf8')
   lines=log_tail(path);self.assertEqual(len(lines),200);self.assertEqual(lines[-1],'Message 999')
   self.assertLess(len('\n'.join(log_tail(path,limit=80))),80)
 def test_unicode_and_markup_are_preserved_as_text(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'process.log';value='VRAM清理完成\n<script>test</script>'
   path.write_text(value,encoding='utf8');self.assertEqual(log_tail(path),value.splitlines())

if __name__=='__main__':unittest.main()
