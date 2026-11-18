"""Operator interface to the same durable film project workflow."""
import argparse
import json
import uuid
from pathlib import Path
from .projects import FilmProjects, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / 'film-projects')
    commands = parser.add_subparsers(dest='operation', required=True)
    create = commands.add_parser('create')
    create.add_argument('spec', type=Path)
    create.add_argument('--creation-id', default=None)
    get = commands.add_parser('get'); get.add_argument('project_id')
    command = commands.add_parser('command')
    command.add_argument('project_id'); command.add_argument('action')
    command.add_argument('--revision', type=int, required=True)
    command.add_argument('--command-id', default=None)
    command.add_argument('--payload', type=Path)
    commands.add_parser('work', help='Process pending CPU commands, then exit')
    attach = commands.add_parser('import-take')
    attach.add_argument('project_id'); attach.add_argument('take_id'); attach.add_argument('video', type=Path)
    attach.add_argument('--revision', type=int, required=True)
    binding = commands.add_parser('bind-input', help='Import a required PNG for separate human review; no inference')
    binding.add_argument('project_id'); binding.add_argument('take_id'); binding.add_argument('name')
    binding.add_argument('image', type=Path); binding.add_argument('--revision', type=int, required=True)
    args = parser.parse_args()
    projects = FilmProjects(args.root)
    if args.operation == 'create':
        result = projects.create(json.loads(args.spec.read_text(encoding='utf8')), args.creation_id or str(uuid.uuid4()))
    elif args.operation == 'get':
        result = projects.get(args.project_id)
    elif args.operation == 'command':
        result = projects.command(args.project_id, {'action': args.action, 'expected_revision': args.revision,
            'command_id': args.command_id or str(uuid.uuid4()),
            'payload': json.loads(args.payload.read_text(encoding='utf8')) if args.payload else {}})
    elif args.operation == 'work':
        count = 0
        while projects.tick():
            count += 1
        result = {'processed': count, 'gpu_policy': 'disabled'}
    elif args.operation == 'bind-input':
        from .project_inputs import bind_image
        result = bind_image(projects, args.project_id, args.take_id, args.name, args.image, args.revision)
    else:
        result = projects.import_take(args.project_id, args.take_id, args.video, args.revision)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
