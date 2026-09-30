# JARVIS

Phase 1 is a small terminal application. It uses only the Python standard library and does not connect to an AI service yet.

## Set up on macOS

From the project directory, create and activate a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

No packages need to be installed for Phase 1. The virtual environment keeps any packages added in later phases separate from the rest of your Mac.

## Run

With the virtual environment active:

```sh
python main.py
```

Type `help` to see the available commands. Type `exit`, `quit`, or `bye` to close JARVIS. Press Control-C to exit as well.

## Test

This feeds the help and exit commands into JARVIS automatically:

```sh
printf 'help\nexit\n' | python main.py
```

Settings can be supplied as environment variables, for example:

```sh
JARVIS_NAME=Alex python main.py
```

Phase 1 has no secrets. `.env` is excluded from Git so credentials can be added safely when a later phase needs them.