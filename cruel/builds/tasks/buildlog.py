import os
PREFIX = '!cruel '
_ACTIVE_FLAGS = frozenset((f for f in os.environ.get('CRUEL_FLAGS', '').split(',') if f))

def flag(name):
    return name in _ACTIVE_FLAGS

def info(text):
    print(text, flush=True)

def warn(text):
    print(f'{PREFIX}warn {text}', flush=True)

def error(text):
    print(f'{PREFIX}error {text}', flush=True)
DIM = '\x1b[2m'
RESET = '\x1b[0m'
CYAN = '\x1b[36m'
LEVEL_EMIT = {'error': error, 'warn': warn}

def frame(path, line=None, col=None, length=1, source_line=None, help=None, level='error'):
    emit = LEVEL_EMIT.get(level, error)
    if line is None:
        emit(f'{DIM} --> {path}{RESET}')
        if help is not None:
            emit(f'{DIM} = {RESET}{CYAN}help{RESET}{DIM}: {help}{RESET}')
        return
    gutter = len(str(line))
    pad = ' ' * gutter
    emit(f'{DIM}{pad} --> {path}:{line}:{col}{RESET}')
    if source_line is not None:
        emit(f'{DIM}{pad} |{RESET}')
        emit(f'{DIM}{line} |{RESET} {source_line}')
        emit(f"{DIM}{pad} |{RESET} {' ' * col}{'^' * max(length, 1)}")
    else:
        emit(f'{DIM}{pad} |{RESET}')
    if help is not None:
        emit(f'{DIM}{pad} = {RESET}{CYAN}help{RESET}{DIM}: {help}{RESET}')

def task_start(task_id, label):
    print(f'{PREFIX}task_start {task_id} {label}', flush=True)

def task_progress(task_id, percent):
    percent = max(0, min(100, int(percent)))
    print(f'{PREFIX}task_progress {task_id} {percent}', flush=True)

def task_done(task_id):
    print(f'{PREFIX}task_done {task_id}', flush=True)

def task_fail(task_id, text):
    print(f'{PREFIX}task_fail {task_id} {text}', flush=True)

class Task:

    def __init__(self, task_id):
        self.task_id = task_id

    def progress(self, percent):
        task_progress(self.task_id, percent)

class task:

    def __init__(self, task_id, label):
        self.task_id = task_id
        self.label = label

    def __enter__(self):
        task_start(self.task_id, self.label)
        return Task(self.task_id)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            task_done(self.task_id)
            return False
        task_fail(self.task_id, str(exc_value))
        return False
