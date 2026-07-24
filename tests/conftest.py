"""pytest config for clip-agent-standalone tests

Pre-mocks the entire app.services.* namespace so standalone tests
can run without the backend. Every clip_agent submodule that gets
imported via 'from app.services.clip_agent.xxx import ...' must be
pre-registered in sys.modules.
"""
import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path for standalone imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def _build_app_modules():
    """Scan clip_agent directory and pre-register all modules under
    app.services.clip_agent.* in sys.modules so that 'from app.services...'
    imports resolve without the backend."""
    clip_dir = src_path / "clip_agent"
    if not clip_dir.exists():
        return

    # List all .py files (exclude __init__
    py_files = [f.stem for f in sorted(clip_dir.glob("*.py"))
                if f.stem != "__init__"]

    # Pre-register app root modules
    for mod in ['app', 'app.services']:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

    # Make app.services.clip_agent a mock package (needs __path__ for submodule resolution)
    clip_pkg = MagicMock()
    clip_pkg.__path__ = [str(clip_dir)]
    clip_pkg.__package__ = 'app.services.clip_agent'
    clip_pkg.__spec__ = MagicMock()
    sys.modules['app.services.clip_agent'] = clip_pkg

    # Register every clip_agent module under app.services.clip_agent.*
    for name in py_files:
        key = f'app.services.clip_agent.{name}'
        if key not in sys.modules:
            sys.modules[key] = MagicMock()

    # Also register commonly referenced backend modules
    for svc in ['shot_splitter', 'video_editor', 'edit_orchestrator',
                'bgm_library', 'model_config', 'gateway_client',
                'compliance', 'credit_service']:
        key = f'app.services.{svc}'
        if key not in sys.modules:
            sys.modules[key] = MagicMock()


_build_app_modules()
