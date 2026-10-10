"""
core/voice_engine.py — Motor de Voz (Wake Word + Whisper)

ESC-06: Cola de audio con queue.Queue
ESC-08: Archivos temporales en tempfile
ESC-09: Despacho via cola de mensajes IA
"""
import os
import time
import glob
import tempfile
import threading
import queue

import numpy
import sounddevice
from scipy.io import wavfile
import faster_whisper
import openwakeword
from openwakeword.model import Model
import pygame
import flet as ft

from config import (
    SAMPLE_RATE,
    WAKEWORD_THRESHOLD,
    SILENCE_THRESHOLD,
    SILENCE_TIMEOUT_SECS,
    MAX_RECORDING_SECS,
    NO_SPEECH_TIMEOUT_SECS,
    WHISPER_MODEL,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
)
from core.cola_mensajes import (
    encolar_peticion,
    esta_en_modo_pesado,
    cancelar_tarea_pesada,
    obtener_tamano_cola,
)

# =============================================================================
# Estado global del motor de audio
# =============================================================================
_carga_modelo = None
_guardiano = None
_mic_guardian = None

# Cola de audio (ESC-06)
_cola_audio = queue.Queue(maxsize=10)


def inicializar_sistemas_audio(page: ft.Page):
    """Inicializa Whisper, wake word model, y micrófono."""
    global _carga_modelo, _guardiano, _mic_guardian

    pygame.mixer.init()
    try:
        openwakeword.utils.download_models()
        _guardiano = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        _carga_modelo = faster_whisper.WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        _mic_guardian = sounddevice.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16")
        _mic_guardian.start()
        page.pubsub.send_all({"tipo": "audio_listo"})
    except Exception as e:
        print(f"Error fatal de audio: {e}")


def motor_jarvis(page: ft.Page, id_peticion_ref: list, procesar_callback):
    """
    Loop principal de escucha: wake word → grabación → transcripción → callback.
    
    Args:
        page: Página Flet para pubsub
        id_peticion_ref: lista [int] mutable con el ID de petición global
        procesar_callback: función(page, texto, usar_voz, id_peticion) para procesar
    """
    while _guardiano is None or _carga_modelo is None:
        time.sleep(1)

    try:
        while True:
            # Limpieza de archivos residuales de TTS en el directorio raíz
            for archivo_basura in glob.glob("respuesta_*.mp3"):
                try:
                    os.remove(archivo_basura)
                except OSError:
                    pass

            # --- Detección de wake word ---
            while True:
                chunk, _ = _mic_guardian.read(1280)
                prediccion = _guardiano.predict(chunk.flatten())
                if prediccion["hey_jarvis"] > WAKEWORD_THRESHOLD:
                    page.pubsub.send_all({"tipo": "onda_escuchando", "estado": True})
                    break

            # --- Grabación de audio ---
            audio_grabado = []
            silencio_acumulado = 0.0
            tiempo_total = 0.0
            ha_hablado = False

            with sounddevice.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as mic_stream:
                while True:
                    chunk, _ = mic_stream.read(int(SAMPLE_RATE * 0.1))
                    audio_grabado.append(chunk)
                    tiempo_total += 0.1

                    if numpy.sqrt(numpy.mean(chunk ** 2)) > SILENCE_THRESHOLD:
                        ha_hablado = True
                        silencio_acumulado = 0.0
                    else:
                        if ha_hablado:
                            silencio_acumulado += 0.1
                        elif tiempo_total > NO_SPEECH_TIMEOUT_SECS:
                            break

                    if silencio_acumulado >= SILENCE_TIMEOUT_SECS or tiempo_total >= MAX_RECORDING_SECS:
                        break

            page.pubsub.send_all({"tipo": "onda_escuchando", "estado": False})

            if not ha_hablado:
                continue

            # --- Transcripción con Whisper (ESC-08: tempfile) ---
            temp_wav = os.path.join(tempfile.gettempdir(), "reaxy_audio_temp.wav")
            wavfile.write(temp_wav, SAMPLE_RATE, numpy.concatenate(audio_grabado, axis=0))
            segmentos, _ = _carga_modelo.transcribe(temp_wav, language="es")
            transcripcion = "".join([s.text + " " for s in segmentos]).strip()

            # Limpiar archivo temporal
            try:
                os.remove(temp_wav)
            except OSError:
                pass

            if transcripcion == "":
                continue

            # --- Comportamiento si llega petición de voz durante Modo Pesado ---
            transcripcion_lower = transcripcion.lower().strip()
            if esta_en_modo_pesado():
                palabras_cancel = ["cancelar", "cancela", "detener", "detén", "detente", "abortar", "stop", "para"]
                if any(p in transcripcion_lower for p in palabras_cancel):
                    cancelar_tarea_pesada()
                    page.pubsub.send_all({
                        "tipo": "respuesta_ia",
                        "texto": f"🛑 [Voz]: '{transcripcion}' detectado. Cancelando tarea en modo pesado...",
                    })
                    continue
                else:
                    # Encolar: La tarea pesada está ocupando Ollama, la petición de voz espera su turno
                    id_peticion_ref[0] += 1
                    page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": transcripcion})
                    page.pubsub.send_all({
                        "tipo": "respuesta_ia",
                        "texto": f"⏳ [Voz]: Modo pesado en ejecución. Tu petición ha sido encolada (turno #{obtener_tamano_cola() + 1}).",
                    })
                    encolar_peticion(
                        procesar_callback,
                        (page, transcripcion, True, id_peticion_ref[0]),
                        page,
                    )
            else:
                # --- Despachar al motor IA via cola (ESC-09) ---
                id_peticion_ref[0] += 1
                page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": transcripcion})
                encolar_peticion(
                    procesar_callback,
                    (page, transcripcion, True, id_peticion_ref[0]),
                    page,
                )

    except KeyboardInterrupt:
        pass


# =============================================================================
# Dictado al campo de texto (Transcripción en tiempo real → UI)
# =============================================================================
_dictando = [False]


def iniciar_dictado(page: ft.Page):
    """
    Activa el dictado: graba audio en chunks cortos, transcribe con Whisper
    y publica cada fragmento en pubsub para que la UI lo inserte en campo_texto.
    """
    if _carga_modelo is None:
        page.pubsub.send_all({
            "tipo": "dictado_chunk",
            "texto": "[Whisper no listo]",
        })
        return

    _dictando[0] = True
    page.pubsub.send_all({"tipo": "dictado_estado", "activo": True})

    import tempfile
    import os
    from scipy.io import wavfile

    try:
        with sounddevice.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as mic:
            buffer_chunks = []
            silencio_acumulado = 0.0
            chunk_duracion = 0.1  # segundos por bloque de lectura

            while _dictando[0]:
                chunk, _ = mic.read(int(SAMPLE_RATE * chunk_duracion))
                buffer_chunks.append(chunk)

                es_silencio = numpy.sqrt(numpy.mean(chunk ** 2)) < SILENCE_THRESHOLD

                if es_silencio:
                    silencio_acumulado += chunk_duracion
                else:
                    silencio_acumulado = 0.0

                # Cada ~2 segundos de silencio ó cada ~3 segundos, transcribimos el buffer
                duracion_buffer = len(buffer_chunks) * chunk_duracion
                if silencio_acumulado >= 1.5 or duracion_buffer >= 3.0:
                    if len(buffer_chunks) > 5:  # mínimo ~0.5s de audio
                        audio_np = numpy.concatenate(buffer_chunks, axis=0)
                        temp_wav = os.path.join(tempfile.gettempdir(), "reaxy_dictado_temp.wav")
                        wavfile.write(temp_wav, SAMPLE_RATE, audio_np)

                        try:
                            segmentos, _ = _carga_modelo.transcribe(temp_wav, language="es")
                            texto = "".join([s.text for s in segmentos]).strip()
                            if texto:
                                page.pubsub.send_all({"tipo": "dictado_chunk", "texto": texto + " "})
                        except Exception:
                            pass
                        finally:
                            try:
                                os.remove(temp_wav)
                            except OSError:
                                pass

                    buffer_chunks = []
                    silencio_acumulado = 0.0

    except Exception as e:
        print(f"Error en dictado: {e}")
    finally:
        _dictando[0] = False
        page.pubsub.send_all({"tipo": "dictado_estado", "activo": False})


def detener_dictado():
    """Señala al loop de dictado que debe detenerse."""
    _dictando[0] = False
