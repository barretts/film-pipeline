"""Transactional project state and durable CPU command queue."""
import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from .project_contract import ProjectError, identifier


class ProjectStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'projects.sqlite3'
        with self.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commands (
                    project_id TEXT NOT NULL, id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    action TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL,
                    response TEXT NOT NULL, error TEXT, spec_hash TEXT,
                    PRIMARY KEY(project_id,id));
            ''')
            if 'spec_hash' not in {r['name'] for r in db.execute('PRAGMA table_info(commands)')}:
                db.execute('ALTER TABLE commands ADD COLUMN spec_hash TEXT')

    @contextlib.contextmanager
    def transaction(self):
        db = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            if db.in_transaction:
                db.commit()
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def read(self, db, project_id):
        identifier(project_id, 'project id')
        row = db.execute('SELECT document FROM projects WHERE id=?', (project_id,)).fetchone()
        if row is None:
            raise ProjectError('Film project not found', 404)
        return json.loads(row['document'])

    def save(self, db, project):
        project['updated'] = time.time()
        db.execute('INSERT OR REPLACE INTO projects(id,document) VALUES (?,?)',
                   (project['project_id'], json.dumps(project, allow_nan=False)))

    def create(self, spec, creation_id):
        identifier(creation_id, 'creation id')
        # Creation ids are stable across retries, including a lost HTTP response.
        project_id = 'film-' + str(uuid.uuid5(uuid.NAMESPACE_URL, creation_id))
        with self.transaction() as db:
            row = db.execute('SELECT document FROM projects WHERE id=?', (project_id,)).fetchone()
            if row:
                known = json.loads(row['document'])
                if known['creation_spec'] != spec:
                    raise ProjectError('Creation id was already used for different content', 409)
                return known
            project = {'schema_version': 1, 'project_id': project_id, 'revision': 1,
                       'created': time.time(), 'status': 'draft', 'gpu_policy': 'disabled',
                       'creation_spec': spec, 'spec': spec, 'preparation': None,
                       'storyboard_approval': None, 'takes': [], 'reviews': [],
                       'artifacts': [], 'cancelled': False}
            self.save(db, project)
            return project

    def get(self, project_id):
        with self.transaction() as db:
            return self.read(db, project_id)

    def list(self):
        with self.transaction() as db:
            return [json.loads(r['document']) for r in db.execute('SELECT document FROM projects ORDER BY rowid DESC')]

    def directory(self, project_id):
        identifier(project_id, 'project id')
        return self.root / project_id
