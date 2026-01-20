"""
groove_extractor/separator.py

Separación de audio en stems de batería individuales.
Usa Demucs para extraer drums y DrumSep para separar componentes.

Pipeline:
    Audio completo → Demucs → drums.wav → DrumSep → kick, snare, hihat, cymbals, toms
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Optional

# Intentar importar audio-separator
try:
    from audio_separator.separator import Separator
    HAS_AUDIO_SEPARATOR = True
except ImportError:
    HAS_AUDIO_SEPARATOR = False
    print("⚠️ audio-separator no instalado. Instalar: pip install audio-separator[cpu]")


class DrumSeparator:
    """
    Separa audio en stems de batería individuales.

    Pipeline:
        1. Demucs: Audio completo → drums.wav
        2. DrumSep: drums.wav → kick, snare, hihat, toms, cymbals

    Uso:
        separator = DrumSeparator(output_dir="./stems")
        stems = separator.process("cancion.wav")
        # stems = {'kick': 'path/to/kick.wav', 'snare': '...', ...}
    """

    # Modelos DrumSep disponibles
    DRUMSEP_MODELS = {
        '6stems': 'drumsep_scnet_xl_6stems.onnx',  # kick, snare, toms, hh, ride, crash
        '5stems': 'drumsep_scnet_xl_5stems.onnx',  # kick, snare, toms, hh, cymbals
        '4stems': 'drumsep_scnet_xl_4stems.onnx',  # kick, snare, toms, cymbals
    }

    # Mapeo de nombres de stems a nombres estándar de Book of Drums
    STEM_TO_INSTRUMENT = {
        'kick': 'kick',
        'bass_drum': 'kick',
        'bd': 'kick',
        'snare': 'snare_crossstick',  # Default a crossstick (más común en reggae)
        'sd': 'snare_crossstick',
        'hihat': 'hihat_closed',
        'hh': 'hihat_closed',
        'hi-hat': 'hihat_closed',
        'hi_hat': 'hihat_closed',
        'toms': 'tom_high',
        'tom': 'tom_high',
        'cymbals': 'ride',  # En reggae, más común es ride
        'cymbal': 'ride',
        'crash': 'crash',
        'ride': 'ride',
    }

    def __init__(self, output_dir: str = "./stems", model: str = "5stems"):
        """
        Args:
            output_dir: Directorio donde guardar los stems
            model: Modelo DrumSep a usar ('5stems', '6stems', '4stems')
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model = self.DRUMSEP_MODELS.get(model, model)

    def separate_with_demucs(self, audio_path: str) -> Optional[Path]:
        """
        Paso 1: Usa Demucs para extraer el stem de batería.

        Args:
            audio_path: Ruta al archivo de audio completo

        Returns:
            Path al archivo drums.wav, o None si falla
        """
        audio_path = Path(audio_path)
        print(f"🥁 [Demucs] Separando batería de: {audio_path.name}")

        demucs_out = self.output_dir / "demucs"

        cmd = [
            "demucs",
            "--two-stems", "drums",
            "-o", str(demucs_out),
            str(audio_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos máximo
            )

            if result.returncode != 0:
                print(f"❌ Error en Demucs: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("❌ Demucs excedió el tiempo límite")
            return None
        except FileNotFoundError:
            print("❌ Demucs no está instalado. Instalar: pip install demucs")
            return None

        # Buscar el output (Demucs usa diferentes nombres de modelo)
        possible_paths = [
            demucs_out / "htdemucs" / audio_path.stem / "drums.wav",
            demucs_out / "htdemucs_ft" / audio_path.stem / "drums.wav",
            demucs_out / "mdx_extra" / audio_path.stem / "drums.wav",
        ]

        for drums_path in possible_paths:
            if drums_path.exists():
                print(f"   ✓ Stem de batería: {drums_path}")
                return drums_path

        # Buscar recursivamente
        for wav_file in demucs_out.rglob("drums.wav"):
            print(f"   ✓ Stem de batería encontrado: {wav_file}")
            return wav_file

        print("❌ No se encontró drums.wav en la salida de Demucs")
        return None

    def separate_drums_components(self, drums_path: str) -> Dict[str, str]:
        """
        Paso 2: Usa DrumSep para separar el stem de batería en componentes.

        Args:
            drums_path: Ruta al archivo drums.wav

        Returns:
            Dict {instrumento: path} con los stems separados
        """
        if not HAS_AUDIO_SEPARATOR:
            raise ImportError(
                "audio-separator no instalado. "
                "Instalar: pip install audio-separator[cpu]"
            )

        drums_path = Path(drums_path)
        print(f"🎛️ [DrumSep] Separando componentes: {drums_path.name}")

        drumsep_out = self.output_dir / "drumsep" / drums_path.stem
        drumsep_out.mkdir(parents=True, exist_ok=True)

        # Crear separador
        separator = Separator(
            output_dir=str(drumsep_out),
            output_format="wav"
        )

        # Cargar modelo DrumSep
        try:
            separator.load_model(self.model)
        except Exception as e:
            print(f"⚠️ No se pudo cargar modelo {self.model}: {e}")
            print("   Intentando con modelo por defecto...")
            separator.load_model()

        # Separar
        try:
            output_files = separator.separate(str(drums_path))
        except Exception as e:
            print(f"❌ Error en DrumSep: {e}")
            return {}

        # Mapear outputs a nombres estándar
        stems = {}

        if isinstance(output_files, dict):
            # El separador devolvió un dict
            for stem_name, path in output_files.items():
                instrument = self._map_stem_to_instrument(stem_name)
                if instrument:
                    stems[instrument] = str(path)
                    print(f"   ✓ {stem_name} → {instrument}")
        else:
            # El separador devolvió lista o string, buscar archivos
            for wav_file in drumsep_out.glob("*.wav"):
                stem_name = wav_file.stem.lower()
                # Limpiar nombre (a veces incluye prefijos)
                for key in self.STEM_TO_INSTRUMENT.keys():
                    if key in stem_name:
                        instrument = self.STEM_TO_INSTRUMENT[key]
                        stems[instrument] = str(wav_file)
                        print(f"   ✓ {wav_file.name} → {instrument}")
                        break

        print(f"   Total stems: {len(stems)}")
        return stems

    def _map_stem_to_instrument(self, stem_name: str) -> Optional[str]:
        """Mapea nombre de stem a nombre de instrumento estándar."""
        stem_lower = stem_name.lower().strip()

        # Buscar match directo o parcial
        for key, instrument in self.STEM_TO_INSTRUMENT.items():
            if key in stem_lower:
                return instrument

        return None

    def process(self, audio_path: str, skip_demucs: bool = False) -> Dict[str, str]:
        """
        Pipeline completo: Audio → Drums → Componentes

        Args:
            audio_path: Ruta al archivo de audio
            skip_demucs: Si True, asume que audio_path ya es un stem de batería

        Returns:
            Dict {instrumento: path} con todos los stems
        """
        audio_path = Path(audio_path)

        if skip_demucs:
            # Usar el audio directamente como drums
            drums_path = audio_path
            print(f"⏭️ Saltando Demucs, usando directamente: {audio_path.name}")
        else:
            # Paso 1: Demucs
            drums_path = self.separate_with_demucs(str(audio_path))
            if drums_path is None:
                print("⚠️ No se pudo extraer batería con Demucs")
                # Intentar usar el audio original
                drums_path = audio_path

        # Paso 2: DrumSep
        try:
            stems = self.separate_drums_components(str(drums_path))
        except ImportError as e:
            print(f"⚠️ {e}")
            # Fallback: usar el audio como "drums" genérico
            stems = {'drums': str(drums_path)}

        return stems

    def get_cached_stems(self, audio_name: str) -> Dict[str, str]:
        """
        Busca stems ya procesados en el directorio de salida.

        Args:
            audio_name: Nombre del archivo de audio (sin extensión)

        Returns:
            Dict {instrumento: path} si existen, {} si no
        """
        drumsep_dir = self.output_dir / "drumsep" / audio_name

        if not drumsep_dir.exists():
            # Intentar sin el sufijo
            for d in (self.output_dir / "drumsep").glob(f"{audio_name}*"):
                if d.is_dir():
                    drumsep_dir = d
                    break

        if not drumsep_dir.exists():
            return {}

        stems = {}
        for wav_file in drumsep_dir.glob("*.wav"):
            instrument = self._map_stem_to_instrument(wav_file.stem)
            if instrument:
                stems[instrument] = str(wav_file)

        return stems


def main():
    """CLI básico para separación de audio."""
    import argparse

    parser = argparse.ArgumentParser(description='Separador de batería (Demucs + DrumSep)')
    parser.add_argument('audio', help='Archivo de audio a separar')
    parser.add_argument('--output', '-o', default='./stems', help='Directorio de salida')
    parser.add_argument('--model', '-m', default='5stems',
                        choices=['4stems', '5stems', '6stems'],
                        help='Modelo DrumSep a usar')
    parser.add_argument('--skip-demucs', action='store_true',
                        help='Saltar Demucs (si el audio ya es solo batería)')

    args = parser.parse_args()

    separator = DrumSeparator(output_dir=args.output, model=args.model)
    stems = separator.process(args.audio, skip_demucs=args.skip_demucs)

    print("\n📁 Stems generados:")
    for instrument, path in stems.items():
        print(f"   {instrument}: {path}")


if __name__ == '__main__':
    main()
