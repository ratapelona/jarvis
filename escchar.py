import faster_whisper
import sounddevice
from scipy.io import wavfile
import numpy


dispositivos_disp=sounddevice.query_devices(1)
print(dispositivos_disp)
hz=16000
seg=5
matriz_len=hz*seg

print("escuchando")

escuchar=sounddevice.rec(
    frames=matriz_len,
    samplerate=hz,
    channels=1,
    dtype="float32",
    device=1
)
sounddevice.wait()
print("Grabación terminada.")
wavfile.write("audio_temporal.wav", hz, escuchar)
print("Archivo guardado en tu disco.")
carga_modelo=faster_whisper.WhisperModel("base",device="cpu",compute_type="int8")

print("transcripcion")

segmentos,info_leng=carga_modelo.transcribe("audio_temporal.wav",language="es",)
print(" Tu texto es:")
for segmento in segmentos:
    print(segmento.text)


