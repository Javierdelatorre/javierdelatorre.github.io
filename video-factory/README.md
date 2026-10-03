# video-factory

Genera videos de YouTube/Shorts de forma automática: **tema viral → guion → voz → animación → mp4**.
Cada etapa es una pieza intercambiable. Todo corre **en tu PC**; tu voz no sale de ella.

```
 temas            guion              voz               animación          video
┌────────┐     ┌───────────┐     ┌────────────┐     ┌──────────────┐    ┌───────┐
│ trends │ ──▶ │ template  │ ──▶ │ silent     │ ──▶ │ kinetic      │ ─▶ │ .mp4  │
│ file   │     │ ollama    │     │ piper      │     │ countdown    │    │ ffmpeg│
│ --topic│     │ claude    │     │ command ★  │     │ slideshow    │    └───────┘
└────────┘     │ --script  │     └────────────┘     └──────────────┘
               └───────────┘      ★ tu voz clonada
```

## Instalación (en tu PC)

```bash
cd video-factory
python -m venv .venv && .venv\Scripts\activate      # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -e ".[dev]"      # incluye ffmpeg: no hace falta instalarlo aparte
python -m vidfactory doctor  # revisa ffmpeg, GPU, voz y guionista
```

## Uso

```bash
python -m vidfactory styles                                   # tipos de animación
python -m vidfactory topics                                   # temas virales propuestos
python -m vidfactory auto --style countdown                   # toma el #1 viral y hace el video
python -m vidfactory auto --pick 3 --style kinetic            # o el tema #3
python -m vidfactory make --topic "Los 3 errores al ahorrar" --style kinetic
python -m vidfactory make --script mi_guion.json --style slideshow
python -m vidfactory batch topics.txt --style kinetic         # un video por línea
```

Añade `--draft` para un borrador a mitad de resolución (ideal para probar un estilo).
Cada video queda en `output/<fecha>-<tema>/` con `video.mp4`, `script.json` y `timings.json`.

## Configuración (`config.toml`)

| Quiero… | Pon en `config.toml` |
|---|---|
| Guiones reales gratis y locales | instala [Ollama](https://ollama.com), `ollama pull llama3.1` y `writer = "ollama"` |
| Guiones con Claude | `writer = "claude"` y la variable de entorno `ANTHROPIC_API_KEY` |
| Voz rápida en CPU | `backend = "piper"` + ruta al `.onnx` en `[voice.piper]` |
| **Mi voz clonada** | `backend = "command"` y en `[voice.command]` los `args` de tu TTS local (XTTS, F5-TTS…) |
| Tendencias de mi país | `geo = "PE"` (o MX, ES, AR, CO…) en `[topics]` |

La voz `silent` (por defecto) **no produce audio**: sirve para probar estilos. Mientras el guionista sea
`template`, el guion es genérico. Para videos reales configura una voz y un guionista.

### Tu voz clonada (`command`)
No dependo de un modelo concreto: tú indicas cómo llamar a tu TTS local. Debe leer el texto, usar tu muestra
y escribir un `.wav` en `{out}`:

```toml
[voice.command]
speaker_wav = "voices/mi_voz.wav"
args = ["python", "mi_tts.py", "--text-file", "{text_file}", "--speaker", "{speaker_wav}", "--language", "{language}", "--out", "{out}"]
```
Cada escena se sintetiza por separado y se **guarda en caché** (`cache/voice/`): si repites el video o
cambias solo un párrafo, solo se regenera lo que cambió.

## ¿Por qué tarda?
Al terminar, el programa imprime cuánto tardó cada etapa y el render en múltiplos de tiempo real:
`tiempos: guion 1.2s | voz 310.0s | render 95.0s`. Así se ve qué etapa es el cuello de botella antes de
cambiar nada. Referencia medida en un sandbox de 4 núcleos **sin GPU**: el render a 1080×1920 va a 0,75× tiempo
real (≈2,5 min para 3 min de video) y a mitad de resolución (`--draft`) ≈0,3×. Con tarjeta NVIDIA,
`encoder = "auto"` usa `h264_nvenc` para codificar. El modelo de voz suele ser la etapa más lenta.

## Crear tu propia pieza

- **Animación nueva:** copia `vidfactory/styles/kinetic.py`, hereda de `Style`, define `frame(index, scene, t)`
  (devuelve una imagen PIL) y decórala con `@STYLES.register("mi_estilo")`. `script_hint` le dice al
  guionista qué forma de guion necesita ese estilo.
- **Voz nueva:** clase en `vidfactory/voice.py` con `synth(text, out_wav)` y `@BACKENDS.register("nombre")`.
- **Guionista nuevo:** función en `vidfactory/scripting.py` con `@WRITERS.register("nombre")`.
- **Fuente de temas nueva:** función en `vidfactory/topics.py` con `@PROVIDERS.register("nombre")`.

Para integrar un motor externo de animación (p. ej. uno basado en HTML/Remotion), se crea un estilo que
renderice con ese motor y devuelva los fotogramas; el resto del flujo no cambia.

## Tests

```bash
python -m pytest
```

## Lo que NO hace (todavía)
- **Subir a YouTube**: no está implementado.
- **Subtítulos sincronizados con reconocimiento de voz**: el momento de cada palabra se reparte según su largo
  (aproximado). Se puede reemplazar por Whisper en `voice.distribute_words`.
- **Leer tendencias en vivo** no se pudo probar en el entorno de desarrollo (red bloqueada); el análisis del
  formato RSS sí está probado.
- **GitHub Actions no sirve para producir** los videos (sin GPU gratis y sus condiciones no lo permiten); la
  producción es en tu PC. El repo solo guarda el código.

## Privacidad
`voices/`, `output/`, `cache/`, `*.wav`, `*.mp4` y `.env` están en `.gitignore`: tu grabación de voz y los videos
no se suben a GitHub. Con `claude` como guionista solo viaja el tema y las instrucciones, nunca audio.
