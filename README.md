# JARVIS

JARVIS is a terminal-based AI assistant. It supports OpenAI text responses, short-lived conversation history, microphone transcription, and spoken replies. Persistent memory, tools, and GUI features are not included.

## Set up on macOS

From the project directory, create and activate a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependency inside the virtual environment:

```sh
python -m pip install -r requirements.txt
```

The virtual environment keeps project packages separate from the rest of your Mac.

## Configure the AI provider

Copy the example environment file and open `.env` in VS Code:

```sh
cp .env.example .env
code .env
```

Replace `your_openai_api_key_here` with your OpenAI API key. Keep `.env` private; Git ignores it. The application reads `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_TRANSCRIPTION_MODEL` from `.env`. The default text model is `gpt-4.1-mini`; transcription uses OpenAI's `gpt-transcribe` model.

## Run

With the virtual environment active, launch with:

```sh
python3 main.py
```

JARVIS first shows a mode menu: choose `1` for text, `2` for voice, or `3` to exit. In text mode, type a question; `voice` switches modes. In voice mode, say `text` to switch back or `exit` to close JARVIS. Type `help` in text mode for local commands. Without an API key, JARVIS still starts, but AI chat and transcription require `OPENAI_API_KEY`.

Check whether the key is configured without displaying it:

```sh
python3 main.py --check-config
```

Voice mode records up to six seconds from the microphone, sends the recording to OpenAI for transcription, sends the resulting text through its normal AI conversation, and speaks the reply using macOS's built-in `say` command. Audio is sent to OpenAI for transcription and is not saved to disk. Allow microphone access for Terminal or VS Code in System Settings > Privacy & Security > Microphone. If access is denied, grant permission and select voice mode again.

## Test

This feeds the help and exit commands into JARVIS automatically (it does not make an API request):

```sh
printf '1\nhelp\nexit\n' | python3 main.py
```

The AI and voice tests run offline and do not need an API key or microphone:

```sh
python -m unittest discover -s tests
```

Settings can also be supplied as environment variables; they override values in `.env`.