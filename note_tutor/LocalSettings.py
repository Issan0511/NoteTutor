"""Load NoteTutor settings without interpolation or logging credentials."""
import os
from pathlib import Path
from dotenv import dotenv_values

ALIASES = {
    'NOTETUTOR_CLAUDE_MODEL': 'BEAMERPLUS_CLAUDE_MODEL',
    'NOTETUTOR_VISION_MODEL': 'BEAMERPLUS_VISION_MODEL',
    'NOTETUTOR_VISION_ENABLED': 'BEAMERPLUS_VISION_ENABLED',
}

def load_local_settings(path=None):
    source = Path(path or os.environ.get('NOTETUTOR_ENV_FILE')
                  or os.environ.get('BEAMERPLUS_ENV_FILE')
                  or Path(__file__).resolve().parent.parent / '.env')
    values = dotenv_values(source, interpolate=False)
    if values.get('ANTHROPIC_API_KEY'):
        os.environ.setdefault('ANTHROPIC_API_KEY', values['ANTHROPIC_API_KEY'])
    for current, legacy in ALIASES.items():
        value = next((mapping[name] for mapping in (os.environ, values)
                      for name in (current, legacy) if mapping.get(name)), None)
        if value:
            os.environ.setdefault(current, value)
        if values.get(legacy):
            os.environ.setdefault(legacy, values[legacy])
